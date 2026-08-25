from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID, uuid4

import sqlalchemy as sa
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session, sessionmaker

from app.platform.security.models import (
    AuthSessionRecord,
    IdentityRecord,
    TotpFactorRecord,
    TotpRecoveryCodeRecord,
)

_TOTP_PERIOD_SECONDS: Final = 30
_TOTP_DIGITS: Final = 6
_TOTP_SECRET_BYTES: Final = 20
_ENROLLMENT_TTL: Final = timedelta(minutes=10)
_RECOVERY_CODE_COUNT: Final = 10


class TotpConfigurationError(ValueError):
    """The server cannot safely use TOTP because its encryption key is invalid."""


class TotpEnrollmentError(ValueError):
    """The enrollment request is not valid for the current identity state."""


class TotpVerificationError(ValueError):
    """The supplied TOTP or recovery code cannot authorize the operation."""


@dataclass(frozen=True, slots=True)
class TotpEnrollmentResult:
    factor_id: UUID
    otpauth_uri: str
    recovery_codes: tuple[str, ...]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class TotpVerificationResult:
    session_id: UUID | None
    used_recovery_code: bool
    verified_at: datetime


class TotpService:
    """Server-side TOTP enrollment and step-up service.

    The seed is encrypted with a Fernet key supplied out of band. Raw recovery
    codes are returned only from enrollment and only their hashes are persisted.
    One TOTP time-step cannot be reused globally for the same factor.
    """

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        encryption_key: str,
        issuer: str = "SMART_AO",
    ) -> None:
        try:
            self._fernet = Fernet(encryption_key.encode("ascii"))
        except (ValueError, TypeError, UnicodeEncodeError) as error:
            raise TotpConfigurationError("invalid TOTP encryption key") from error
        normalized_issuer = issuer.strip()
        if not normalized_issuer or len(normalized_issuer) > 64:
            raise TotpConfigurationError("invalid TOTP issuer")
        self._session_factory = session_factory
        self._issuer = normalized_issuer

    @classmethod
    def from_environment(
        cls, *, session_factory: sessionmaker[Session]
    ) -> TotpService | None:
        raw_key = os.getenv("SMART_AO_TOTP_ENCRYPTION_KEY", "").strip()
        if not raw_key:
            return None
        return cls(
            session_factory=session_factory,
            encryption_key=raw_key,
            issuer=os.getenv("SMART_AO_TOTP_ISSUER", "SMART_AO"),
        )

    def begin_enrollment(
        self, *, identity_id: UUID, now: datetime
    ) -> TotpEnrollmentResult:
        current = _utc(now)
        secret = _new_secret()
        recovery_codes = tuple(_new_recovery_code() for _ in range(_RECOVERY_CODE_COUNT))
        factor_id = uuid4()
        expires_at = current + _ENROLLMENT_TTL
        with self._session_factory.begin() as session:
            identity = session.scalar(
                sa.select(IdentityRecord)
                .where(IdentityRecord.id == identity_id)
                .with_for_update()
            )
            if identity is None or identity.lifecycle != "ACTIVE":
                raise TotpEnrollmentError("IDENTITY_NOT_ACTIVE")
            account_email = identity.email_normalized
            active = session.scalar(
                sa.select(TotpFactorRecord)
                .where(
                    TotpFactorRecord.identity_id == identity_id,
                    TotpFactorRecord.state == "ACTIVE",
                )
                .with_for_update()
            )
            if active is not None:
                raise TotpEnrollmentError("TOTP_ALREADY_ENABLED")
            session.execute(
                sa.update(TotpFactorRecord)
                .where(
                    TotpFactorRecord.identity_id == identity_id,
                    TotpFactorRecord.state == "PENDING",
                )
                .values(state="DISABLED", confirmed_at=current)
            )
            factor = TotpFactorRecord(
                id=factor_id,
                identity_id=identity_id,
                encrypted_secret=self._fernet.encrypt(secret.encode("ascii")).decode("ascii"),
                state="PENDING",
                created_at=current,
                expires_at=expires_at,
                confirmed_at=None,
                last_used_step=None,
            )
            session.add(factor)
            session.add_all(
                TotpRecoveryCodeRecord(
                    id=uuid4(),
                    factor_id=factor_id,
                    code_hash=_hash_recovery_code(code),
                    created_at=current,
                    used_at=None,
                )
                for code in recovery_codes
            )
        return TotpEnrollmentResult(
            factor_id=factor_id,
            otpauth_uri=_otpauth_uri(
                secret=secret,
                issuer=self._issuer,
                account=account_email,
            ),
            recovery_codes=recovery_codes,
            expires_at=expires_at,
        )

    def confirm_enrollment(
        self,
        *,
        identity_id: UUID,
        factor_id: UUID,
        code: str,
        now: datetime,
        session_id: UUID | None = None,
    ) -> datetime:
        current = _utc(now)
        with self._session_factory.begin() as session:
            factor = session.scalar(
                sa.select(TotpFactorRecord)
                .where(
                    TotpFactorRecord.id == factor_id,
                    TotpFactorRecord.identity_id == identity_id,
                )
                .with_for_update()
            )
            if factor is None or factor.state != "PENDING":
                raise TotpVerificationError("TOTP_ENROLLMENT_NOT_PENDING")
            if factor.expires_at <= current:
                factor.state = "DISABLED"
                factor.confirmed_at = current
                raise TotpVerificationError("TOTP_ENROLLMENT_EXPIRED")
            secret = self._decrypt_secret(factor.encrypted_secret)
            counter = _matching_counter(secret=secret, code=code, now=current)
            if counter is None:
                raise TotpVerificationError("TOTP_CODE_INVALID")
            factor.state = "ACTIVE"
            factor.confirmed_at = current
            factor.last_used_step = counter
            if session_id is not None:
                auth_session = session.scalar(
                    sa.select(AuthSessionRecord)
                    .where(
                        AuthSessionRecord.id == session_id,
                        AuthSessionRecord.identity_id == identity_id,
                        AuthSessionRecord.state == "ACTIVE",
                    )
                    .with_for_update()
                )
                if auth_session is None:
                    raise TotpVerificationError("SESSION_NOT_ACTIVE")
                auth_session.mfa_verified_at = current
                auth_session.auth_strength = "MFA"
            return current

    def verify_step_up(
        self, *, session_id: UUID, code: str, now: datetime
    ) -> TotpVerificationResult:
        current = _utc(now)
        with self._session_factory.begin() as session:
            auth_session = session.scalar(
                sa.select(AuthSessionRecord)
                .where(AuthSessionRecord.id == session_id)
                .with_for_update()
            )
            if auth_session is None or auth_session.state != "ACTIVE":
                raise TotpVerificationError("SESSION_NOT_ACTIVE")
            factor = session.scalar(
                sa.select(TotpFactorRecord)
                .where(
                    TotpFactorRecord.identity_id == auth_session.identity_id,
                    TotpFactorRecord.state == "ACTIVE",
                )
                .with_for_update()
            )
            if factor is None:
                raise TotpVerificationError("TOTP_NOT_ENABLED")
            secret = self._decrypt_secret(factor.encrypted_secret)
            counter = _matching_counter(secret=secret, code=code, now=current)
            if counter is not None and factor.last_used_step == counter:
                counter = None
            if counter is not None:
                factor.last_used_step = counter
                auth_session.mfa_verified_at = current
                auth_session.auth_strength = "MFA_STEP_UP"
                return TotpVerificationResult(
                    session_id=session_id,
                    used_recovery_code=False,
                    verified_at=current,
                )
            recovery = _find_recovery_code(session, factor_id=factor.id, code=code)
            if recovery is None:
                raise TotpVerificationError("TOTP_CODE_INVALID")
            recovery.used_at = current
            auth_session.mfa_verified_at = current
            auth_session.auth_strength = "MFA_STEP_UP"
            return TotpVerificationResult(
                session_id=session_id,
                used_recovery_code=True,
                verified_at=current,
            )

    def disable(self, *, identity_id: UUID, code: str, now: datetime) -> None:
        current = _utc(now)
        with self._session_factory.begin() as session:
            factor = session.scalar(
                sa.select(TotpFactorRecord)
                .where(
                    TotpFactorRecord.identity_id == identity_id,
                    TotpFactorRecord.state == "ACTIVE",
                )
                .with_for_update()
            )
            if factor is None:
                raise TotpVerificationError("TOTP_NOT_ENABLED")
            secret = self._decrypt_secret(factor.encrypted_secret)
            counter = _matching_counter(secret=secret, code=code, now=current)
            valid = counter is not None and factor.last_used_step != counter
            if not valid:
                recovery = _find_recovery_code(session, factor_id=factor.id, code=code)
                if recovery is not None:
                    recovery.used_at = current
                    valid = True
            if not valid:
                raise TotpVerificationError("TOTP_CODE_INVALID")
            factor.state = "DISABLED"
            session.execute(
                sa.update(AuthSessionRecord)
                .where(
                    AuthSessionRecord.identity_id == identity_id,
                    AuthSessionRecord.state == "ACTIVE",
                )
                .values(auth_strength="PASSWORD", mfa_verified_at=None)
            )

    def _decrypt_secret(self, encrypted_secret: str) -> str:
        try:
            return self._fernet.decrypt(encrypted_secret.encode("ascii")).decode("ascii")
        except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError) as error:
            raise TotpVerificationError("TOTP_SECRET_UNAVAILABLE") from error


def _new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(_TOTP_SECRET_BYTES)).decode("ascii").rstrip("=")


def _new_recovery_code() -> str:
    raw = secrets.token_hex(8).upper()
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def _hash_recovery_code(code: str) -> str:
    normalized = code.replace("-", "").strip().upper()
    return hashlib.sha256(normalized.encode("ascii")).hexdigest()


def _find_recovery_code(
    session: Session, *, factor_id: UUID, code: str
) -> TotpRecoveryCodeRecord | None:
    try:
        code_hash = _hash_recovery_code(code)
    except (UnicodeEncodeError, ValueError):
        return None
    return session.scalar(
        sa.select(TotpRecoveryCodeRecord)
        .where(
            TotpRecoveryCodeRecord.factor_id == factor_id,
            TotpRecoveryCodeRecord.code_hash == code_hash,
            TotpRecoveryCodeRecord.used_at.is_(None),
        )
        .with_for_update()
    )


def _matching_counter(*, secret: str, code: str, now: datetime) -> int | None:
    normalized = code.strip()
    if len(normalized) != _TOTP_DIGITS or not normalized.isdigit():
        return None
    counter = int(_utc(now).timestamp()) // _TOTP_PERIOD_SECONDS
    for candidate in (counter - 1, counter, counter + 1):
        if hmac.compare_digest(_totp_code(secret, candidate), normalized):
            return candidate
    return None


def _totp_code(secret: str, counter: int) -> str:
    padded = secret + "=" * (-len(secret) % 8)
    key = base64.b32decode(padded, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{binary % (10**_TOTP_DIGITS):0{_TOTP_DIGITS}d}"


def _otpauth_uri(*, secret: str, issuer: str, account: str) -> str:
    from urllib.parse import quote

    label = quote(f"{issuer}:{account}", safe="")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer, safe='')}"
        f"&algorithm=SHA1&digits={_TOTP_DIGITS}&period={_TOTP_PERIOD_SECONDS}"
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("TOTP timestamps must be timezone-aware")
    return value.astimezone(UTC)

"""Transactional SEC-01 authentication services without any HTTP dependency."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

import sqlalchemy as sa
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy.orm import Session, sessionmaker

from app.platform.security.audit import (
    AuditEventType,
    AuditOutcome,
    AuditSeverity,
    SecurityAuditEntry,
    SecurityAuditWriter,
)
from app.platform.security.models import (
    AuthSessionRecord,
    IdentityRecord,
    PasswordCredentialRecord,
    RefreshTokenFamilyRecord,
    RefreshTokenRecord,
    TenantMembershipRecord,
)

_SESSION_IDLE_TIMEOUT = timedelta(hours=8)
_STANDARD_SESSION_ABSOLUTE_TIMEOUT = timedelta(hours=24)
_PRIVILEGED_SESSION_ABSOLUTE_TIMEOUT = timedelta(hours=12)
_PRIVILEGED_ROLES = frozenset({"PATRON_ADMIN", "PATRON_DELEGATE"})
_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$Giaw2rZ3fORtgw8cIuC7iA$"
    "oW9YGrFNwJNdZHzh85jLctFhMFXdAq9A94ZYN9gzh7Y"  # pragma: allowlist secret
)


class PasswordVerifier(Protocol):
    """Verifies an existing password credential without revealing its representation."""

    def verify(self, *, password_hash: str, password: str) -> bool: ...


class OpaqueTokenGenerator(Protocol):
    """Generates an unpredictable browser refresh-token value."""

    def generate(self) -> str: ...


class Clock(Protocol):
    """Returns the current UTC instant, replaceable in deterministic tests."""

    def now(self) -> datetime: ...


class UtcClock:
    """Production clock returning timezone-aware UTC timestamps."""

    def now(self) -> datetime:
        return datetime.now(tz=UTC)


class Argon2idPasswordVerifier:
    """Argon2id-only verifier for stored password credentials."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher(type=Type.ID)

    def verify(self, *, password_hash: str, password: str) -> bool:
        if not password_hash.startswith("$argon2id$"):
            return False
        try:
            return self._hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False


class SecureOpaqueTokenGenerator:
    """Generates a high-entropy refresh token that is never persisted raw."""

    def generate(self) -> str:
        return secrets.token_urlsafe(48)


class InvalidCredentialsError(Exception):
    """Neutral login refusal that intentionally discloses no account state."""

    def __init__(self) -> None:
        super().__init__("INVALID_CREDENTIALS")


class RefreshRejectedError(Exception):
    """Neutral refresh refusal, including absent, expired or replayed tokens."""

    def __init__(self) -> None:
        super().__init__("REFRESH_REJECTED")


@dataclass(frozen=True, slots=True)
class LoginResult:
    """Session references plus the one-time raw refresh value for the caller."""

    identity_id: UUID
    membership_id: UUID
    session_id: UUID
    token_version: int
    refresh_family_id: UUID
    refresh_token_id: UUID
    refresh_token: str
    session_expires_at: datetime
    session_absolute_expires_at: datetime


@dataclass(frozen=True, slots=True)
class RefreshResult:
    """The next refresh value after an atomic one-time rotation."""

    identity_id: UUID
    session_id: UUID
    token_version: int
    refresh_family_id: UUID
    refresh_token_id: UUID
    refresh_token: str
    session_expires_at: datetime
    session_absolute_expires_at: datetime


@dataclass(frozen=True, slots=True)
class AuditedAuthenticationService:
    """Decorates authentication flows with minimized append-only audit events."""

    core: AuthenticationService
    session_factory: sessionmaker[Session]
    writer: SecurityAuditWriter
    clock: Clock

    def login(self, *, email: str, password: str, tenant_id: UUID) -> LoginResult:
        try:
            result = self.core.login(email=email, password=password, tenant_id=tenant_id)
        except InvalidCredentialsError:
            self._record(
                event_type=AuditEventType.AUTH_LOGIN_DENIED,
                outcome=AuditOutcome.DENIED,
                severity=AuditSeverity.WARNING,
                action="auth.login",
                reason_code="INVALID_CREDENTIALS",
            )
            raise
        self._record_for_session(
            session_id=result.session_id,
            event_type=AuditEventType.AUTH_LOGIN_SUCCEEDED,
            outcome=AuditOutcome.SUCCEEDED,
            severity=AuditSeverity.INFO,
            action="auth.login",
            reason_code=None,
        )
        return result

    def logout(self, *, session_id: UUID) -> bool:
        snapshot = self._snapshot(session_id=session_id)
        completed = self.core.logout(session_id=session_id)
        if completed and snapshot is not None:
            self._record(
                tenant_id=snapshot.tenant_id,
                identity_id=snapshot.identity_id,
                session_id=snapshot.id,
                event_type=AuditEventType.AUTH_LOGOUT_SUCCEEDED,
                outcome=AuditOutcome.SUCCEEDED,
                severity=AuditSeverity.INFO,
                action="auth.logout",
                reason_code="LOGOUT",
            )
        return completed

    def refresh(self, *, refresh_token: str) -> RefreshResult:
        try:
            result = self.core.refresh(refresh_token=refresh_token)
        except RefreshRejectedError:
            self._record(
                event_type=AuditEventType.AUTH_REFRESH_DENIED,
                outcome=AuditOutcome.DENIED,
                severity=AuditSeverity.WARNING,
                action="auth.refresh",
                reason_code="REFRESH_REJECTED",
            )
            raise
        self._record_for_session(
            session_id=result.session_id,
            event_type=AuditEventType.AUTH_REFRESH_SUCCEEDED,
            outcome=AuditOutcome.SUCCEEDED,
            severity=AuditSeverity.INFO,
            action="auth.refresh",
            reason_code=None,
        )
        return result

    def _record_for_session(
        self,
        *,
        session_id: UUID,
        event_type: AuditEventType,
        outcome: AuditOutcome,
        severity: AuditSeverity,
        action: str,
        reason_code: str | None,
    ) -> None:
        snapshot = self._snapshot(session_id=session_id)
        if snapshot is None:
            return
        self._record(
            tenant_id=snapshot.tenant_id,
            identity_id=snapshot.identity_id,
            session_id=snapshot.id,
            event_type=event_type,
            outcome=outcome,
            severity=severity,
            action=action,
            reason_code=reason_code,
        )

    def _snapshot(self, *, session_id: UUID) -> AuthSessionRecord | None:
        with self.session_factory() as session:
            return session.get(AuthSessionRecord, session_id)

    def _record(
        self,
        *,
        event_type: AuditEventType,
        outcome: AuditOutcome,
        severity: AuditSeverity,
        action: str,
        reason_code: str | None,
        tenant_id: UUID | None = None,
        identity_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> None:
        with self.session_factory.begin() as session:
            self.writer.record(
                session=session,
                entry=SecurityAuditEntry(
                    occurred_at=self._now(),
                    tenant_id=tenant_id,
                    actor_id=identity_id,
                    identity_id=identity_id,
                    session_id=session_id,
                    actor_kind=None,
                    auth_strength=None,
                    event_type=event_type,
                    outcome=outcome,
                    severity=severity,
                    action=action,
                    resource_type="AUTH_SESSION" if session_id is not None else "AUTHENTICATION",
                    resource_id=session_id,
                    case_id=None,
                    correlation_id=None,
                    command_id=None,
                    request_id=None,
                    source_ip_hash=None,
                    user_agent_family=None,
                    reason_code=reason_code,
                    metadata={"channel": "service"},
                ),
            )

    def _now(self) -> datetime:
        current = self.clock.now()
        if current.tzinfo is None:
            raise ValueError("audit clock must return a timezone-aware timestamp")
        return current.astimezone(UTC)


class AuthenticationService:
    """Implements SEC-01 login, logout and rotating refresh transactions."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        password_verifier: PasswordVerifier,
        token_generator: OpaqueTokenGenerator,
        clock: Clock,
    ) -> None:
        self._session_factory = session_factory
        self._password_verifier = password_verifier
        self._token_generator = token_generator
        self._clock = clock

    def login(self, *, email: str, password: str, tenant_id: UUID) -> LoginResult:
        """Verify an active tenant membership and create a complete login lineage."""
        normalized_email = email.strip().lower()
        now = self._now()
        with self._session_factory.begin() as session:
            candidate = session.execute(
                sa.select(IdentityRecord, PasswordCredentialRecord, TenantMembershipRecord)
                .join(
                    PasswordCredentialRecord,
                    PasswordCredentialRecord.identity_id == IdentityRecord.id,
                )
                .join(
                    TenantMembershipRecord,
                    TenantMembershipRecord.identity_id == IdentityRecord.id,
                )
                .where(
                    IdentityRecord.email_normalized == normalized_email,
                    IdentityRecord.lifecycle == "ACTIVE",
                    TenantMembershipRecord.tenant_id == tenant_id,
                    TenantMembershipRecord.state == "ACTIVE",
                )
                .with_for_update()
            ).one_or_none()
            if candidate is None:
                self._password_verifier.verify(
                    password_hash=_DUMMY_PASSWORD_HASH,
                    password=password,
                )
                raise InvalidCredentialsError()

            identity, credential, membership = candidate
            if credential.algorithm != "ARGON2ID" or not self._password_verifier.verify(
                password_hash=credential.password_hash,
                password=password,
            ):
                raise InvalidCredentialsError()

            absolute_expires_at = now + self._absolute_timeout_for(membership.role)
            session_expires_at = min(now + _SESSION_IDLE_TIMEOUT, absolute_expires_at)
            auth_session = AuthSessionRecord(
                id=uuid4(),
                tenant_id=membership.tenant_id,
                membership_id=membership.id,
                identity_id=identity.id,
                state="ACTIVE",
                auth_strength="PASSWORD",
                token_version=1,
                issued_at=now,
                last_seen_at=now,
                expires_at=session_expires_at,
                absolute_expires_at=absolute_expires_at,
                mfa_verified_at=None,
                revoked_at=None,
                revoke_reason=None,
            )
            refresh_family = RefreshTokenFamilyRecord(
                id=uuid4(),
                tenant_id=membership.tenant_id,
                session_id=auth_session.id,
                state="ACTIVE",
                issued_at=now,
                expires_at=absolute_expires_at,
                revoked_at=None,
                revoke_reason=None,
            )
            raw_refresh_token = self._token_generator.generate()
            refresh_token = RefreshTokenRecord(
                id=uuid4(),
                tenant_id=membership.tenant_id,
                family_id=refresh_family.id,
                parent_token_id=None,
                token_hash=_hash_token(raw_refresh_token),
                state="ACTIVE",
                issued_at=now,
                expires_at=absolute_expires_at,
                consumed_at=None,
                revoked_at=None,
            )
            session.add_all((auth_session, refresh_family, refresh_token))

            return LoginResult(
                identity_id=identity.id,
                membership_id=membership.id,
                session_id=auth_session.id,
                token_version=auth_session.token_version,
                refresh_family_id=refresh_family.id,
                refresh_token_id=refresh_token.id,
                refresh_token=raw_refresh_token,
                session_expires_at=session_expires_at,
                session_absolute_expires_at=absolute_expires_at,
            )

    def logout(self, *, session_id: UUID) -> bool:
        """Revoke an active session, its family and every still-active refresh token."""
        now = self._now()
        with self._session_factory.begin() as session:
            auth_session = session.scalar(
                sa.select(AuthSessionRecord)
                .where(AuthSessionRecord.id == session_id)
                .with_for_update()
            )
            if auth_session is None or auth_session.state != "ACTIVE":
                return False

            refresh_family = session.scalar(
                sa.select(RefreshTokenFamilyRecord)
                .where(RefreshTokenFamilyRecord.session_id == auth_session.id)
                .with_for_update()
            )
            self._revoke_session(auth_session, now=now, reason="LOGOUT")
            if refresh_family is not None:
                self._revoke_family_and_active_tokens(
                    session,
                    family=refresh_family,
                    now=now,
                    state="REVOKED",
                    reason="LOGOUT",
                )
            return True

    def refresh(self, *, refresh_token: str) -> RefreshResult:
        """Rotate one active refresh token or compromise its session lineage on replay."""
        now = self._now()
        token_hash = _hash_token(refresh_token)
        replay_detected = False
        invalidation_detected = False
        with self._session_factory.begin() as session:
            current_token = session.scalar(
                sa.select(RefreshTokenRecord)
                .where(RefreshTokenRecord.token_hash == token_hash)
                .with_for_update()
            )
            if current_token is None:
                raise RefreshRejectedError()

            refresh_family = session.scalar(
                sa.select(RefreshTokenFamilyRecord)
                .where(RefreshTokenFamilyRecord.id == current_token.family_id)
                .with_for_update()
            )
            auth_session = (
                session.scalar(
                    sa.select(AuthSessionRecord)
                    .where(AuthSessionRecord.id == refresh_family.session_id)
                    .with_for_update()
                )
                if refresh_family is not None
                else None
            )
            if refresh_family is None or auth_session is None:
                raise RefreshRejectedError()

            if current_token.state == "ROTATED" and refresh_family.state == "ACTIVE":
                self._compromise_lineage(session, auth_session, refresh_family, now)
                replay_detected = True
            elif current_token.state != "ACTIVE":
                raise RefreshRejectedError()
            else:
                membership = session.scalar(
                    sa.select(TenantMembershipRecord)
                    .where(TenantMembershipRecord.id == auth_session.membership_id)
                    .with_for_update()
                )
                identity = session.scalar(
                    sa.select(IdentityRecord)
                    .where(IdentityRecord.id == auth_session.identity_id)
                    .with_for_update()
                )
                if not self._lineage_is_refreshable(
                    auth_session=auth_session,
                    refresh_family=refresh_family,
                    current_token=current_token,
                    membership=membership,
                    identity=identity,
                    now=now,
                ):
                    self._invalidate_lineage(session, auth_session, refresh_family, now)
                    invalidation_detected = True
                else:
                    current_token.state = "ROTATED"
                    current_token.consumed_at = now
                    session.flush()

                    next_session_expires_at = min(
                        now + _SESSION_IDLE_TIMEOUT,
                        auth_session.absolute_expires_at,
                    )
                    auth_session.last_seen_at = now
                    auth_session.expires_at = next_session_expires_at
                    raw_next_token = self._token_generator.generate()
                    next_token = RefreshTokenRecord(
                        id=uuid4(),
                        tenant_id=current_token.tenant_id,
                        family_id=refresh_family.id,
                        parent_token_id=current_token.id,
                        token_hash=_hash_token(raw_next_token),
                        state="ACTIVE",
                        issued_at=now,
                        expires_at=refresh_family.expires_at,
                        consumed_at=None,
                        revoked_at=None,
                    )
                    session.add(next_token)

                    return RefreshResult(
                        identity_id=auth_session.identity_id,
                        session_id=auth_session.id,
                        token_version=auth_session.token_version,
                        refresh_family_id=refresh_family.id,
                        refresh_token_id=next_token.id,
                        refresh_token=raw_next_token,
                        session_expires_at=next_session_expires_at,
                        session_absolute_expires_at=auth_session.absolute_expires_at,
                    )

        if replay_detected or invalidation_detected:
            raise RefreshRejectedError()
        raise AssertionError("refresh flow ended without a result")

    @staticmethod
    def _absolute_timeout_for(role: str) -> timedelta:
        if role in _PRIVILEGED_ROLES:
            return _PRIVILEGED_SESSION_ABSOLUTE_TIMEOUT
        return _STANDARD_SESSION_ABSOLUTE_TIMEOUT

    @staticmethod
    def _lineage_is_refreshable(
        *,
        auth_session: AuthSessionRecord,
        refresh_family: RefreshTokenFamilyRecord,
        current_token: RefreshTokenRecord,
        membership: TenantMembershipRecord | None,
        identity: IdentityRecord | None,
        now: datetime,
    ) -> bool:
        return (
            auth_session.state == "ACTIVE"
            and refresh_family.state == "ACTIVE"
            and membership is not None
            and membership.state == "ACTIVE"
            and identity is not None
            and identity.lifecycle == "ACTIVE"
            and now < auth_session.expires_at
            and now < auth_session.absolute_expires_at
            and now < refresh_family.expires_at
            and now < current_token.expires_at
        )

    @staticmethod
    def _revoke_session(auth_session: AuthSessionRecord, *, now: datetime, reason: str) -> None:
        auth_session.state = "REVOKED"
        auth_session.revoked_at = now
        auth_session.revoke_reason = reason
        auth_session.token_version += 1

    def _compromise_lineage(
        self,
        session: Session,
        auth_session: AuthSessionRecord,
        refresh_family: RefreshTokenFamilyRecord,
        now: datetime,
    ) -> None:
        self._revoke_session(auth_session, now=now, reason="REFRESH_REPLAY")
        self._revoke_family_and_active_tokens(
            session,
            family=refresh_family,
            now=now,
            state="COMPROMISED",
            reason="REFRESH_REPLAY",
        )

    def _invalidate_lineage(
        self,
        session: Session,
        auth_session: AuthSessionRecord,
        refresh_family: RefreshTokenFamilyRecord,
        now: datetime,
    ) -> None:
        if now >= auth_session.absolute_expires_at or now >= refresh_family.expires_at:
            auth_session.state = "EXPIRED"
            refresh_family.state = "EXPIRED"
            self._expire_active_tokens(session, family_id=refresh_family.id)
            return
        self._revoke_session(auth_session, now=now, reason="AUTH_CONTEXT_INVALID")
        self._revoke_family_and_active_tokens(
            session,
            family=refresh_family,
            now=now,
            state="REVOKED",
            reason="AUTH_CONTEXT_INVALID",
        )

    @staticmethod
    def _revoke_family_and_active_tokens(
        session: Session,
        *,
        family: RefreshTokenFamilyRecord,
        now: datetime,
        state: str,
        reason: str,
    ) -> None:
        family.state = state
        family.revoked_at = now
        family.revoke_reason = reason
        active_tokens = session.scalars(
            sa.select(RefreshTokenRecord)
            .where(
                RefreshTokenRecord.family_id == family.id,
                RefreshTokenRecord.state == "ACTIVE",
            )
            .with_for_update()
        ).all()
        for active_token in active_tokens:
            active_token.state = "REVOKED"
            active_token.revoked_at = now

    @staticmethod
    def _expire_active_tokens(session: Session, *, family_id: UUID) -> None:
        active_tokens = session.scalars(
            sa.select(RefreshTokenRecord)
            .where(
                RefreshTokenRecord.family_id == family_id,
                RefreshTokenRecord.state == "ACTIVE",
            )
            .with_for_update()
        ).all()
        for active_token in active_tokens:
            active_token.state = "EXPIRED"

    def _now(self) -> datetime:
        current = self._clock.now()
        if current.tzinfo is None:
            raise ValueError("authentication clock must return a timezone-aware timestamp")
        return current.astimezone(UTC)


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

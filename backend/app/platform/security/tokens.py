"""Signed short-lived access-token codec with no authorization claims."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError

_ACCESS_TOKEN_TTL = timedelta(minutes=15)


class Clock(Protocol):
    """Returns a timezone-aware current instant."""

    def now(self) -> datetime: ...


class AccessTokenRejectedError(Exception):
    """Neutral access-token refusal that never exposes verification detail."""

    def __init__(self) -> None:
        super().__init__("UNAUTHENTICATED")


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Non-authoritative identity and session claims from a verified JWT."""

    subject: UUID
    session_id: UUID
    token_version: int
    issued_at: datetime
    expires_at: datetime
    token_id: UUID


class JwtAccessTokenCodec:
    """Issues and verifies HS256 access tokens with the SEC-01 claim set."""

    def __init__(
        self,
        *,
        signing_key: str,
        issuer: str,
        audience: str,
        clock: Clock,
        token_ttl: timedelta = _ACCESS_TOKEN_TTL,
        signing_key_id: str = "active",
        verification_keys: Mapping[str, str] | None = None,
    ) -> None:
        if len(signing_key) < 32:
            raise ValueError("JWT signing key must contain at least 32 characters")
        if token_ttl <= timedelta():
            raise ValueError("JWT access token TTL must be positive")
        if not signing_key_id or len(signing_key_id) > 64:
            raise ValueError("JWT signing key id must be 1-64 characters")
        if not all(character.isalnum() or character in "._-" for character in signing_key_id):
            raise ValueError("JWT signing key id contains invalid characters")
        keys = dict(verification_keys or {})
        keys.setdefault(signing_key_id, signing_key)
        if any(len(candidate) < 32 for candidate in keys.values()):
            raise ValueError("JWT verification keys must contain at least 32 characters")
        self._signing_key = signing_key
        self._signing_key_id = signing_key_id
        self._verification_keys = keys
        self._issuer = issuer
        self._audience = audience
        self._clock = clock
        self._token_ttl = token_ttl

    def issue(self, *, identity_id: UUID, session_id: UUID, token_version: int) -> str:
        """Create a short-lived access token with no tenant, role or permission claim."""
        now = self._now()
        expires_at = now + self._token_ttl
        return jwt.encode(
            {
                "iss": self._issuer,
                "aud": self._audience,
                "sub": str(identity_id),
                "sid": str(session_id),
                "jti": str(uuid4()),
                "iat": int(now.timestamp()),
                "exp": int(expires_at.timestamp()),
                "ver": token_version,
            },
            self._signing_key,
            algorithm="HS256",
            headers={"kid": self._signing_key_id},
        )

    def decode(self, token: str) -> AccessTokenClaims:
        """Verify signature, issuer, audience and shape before returning typed claims."""
        try:
            header = jwt.get_unverified_header(token)
            key_id = header.get("kid", self._signing_key_id)
            if not isinstance(key_id, str):
                raise AccessTokenRejectedError()
            verification_key = self._verification_keys.get(key_id)
            if verification_key is None:
                raise AccessTokenRejectedError()
            payload = jwt.decode(
                token,
                verification_key,
                algorithms=["HS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={
                    "require": ["iss", "aud", "sub", "sid", "jti", "iat", "exp", "ver"],
                    "verify_exp": False,
                    "verify_iat": False,
                },
            )
            claims = AccessTokenClaims(
                subject=UUID(payload["sub"]),
                session_id=UUID(payload["sid"]),
                token_version=int(payload["ver"]),
                issued_at=datetime.fromtimestamp(int(payload["iat"]), tz=UTC),
                expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
                token_id=UUID(payload["jti"]),
            )
        except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
            raise AccessTokenRejectedError() from error
        now = self._now()
        if (
            claims.token_version < 1
            or claims.issued_at > now
            or claims.expires_at <= now
        ):
            raise AccessTokenRejectedError()
        return claims

    def _now(self) -> datetime:
        current = self._clock.now()
        if current.tzinfo is None:
            raise ValueError("access-token clock must return a timezone-aware timestamp")
        return current.astimezone(UTC)

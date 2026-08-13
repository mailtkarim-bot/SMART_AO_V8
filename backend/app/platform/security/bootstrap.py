"""Atomic local provisioning and first-patron bootstrap services for SEC-01."""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

import sqlalchemy as sa
from argon2 import PasswordHasher, Type
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.platform.persistence.models import TenantRecord
from app.platform.security.models import (
    IdentityRecord,
    PasswordCredentialRecord,
    TenantBootstrapTokenRecord,
    TenantMembershipRecord,
)

_BOOTSTRAP_TOKEN_TTL = timedelta(hours=1)
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,119}$")


class PasswordCredentialHasher(Protocol):
    """Creates the non-reversible Argon2id credential for an initial password."""

    def hash(self, password: str) -> str: ...


class BootstrapSecretGenerator(Protocol):
    """Generates the one-time secret returned only to the local installer."""

    def generate(self) -> str: ...


class Clock(Protocol):
    """Returns the current timezone-aware instant."""

    def now(self) -> datetime: ...


class UtcClock:
    """Production UTC clock."""

    def now(self) -> datetime:
        return datetime.now(tz=UTC)


class Argon2idPasswordCredentialHasher:
    """Initial password hasher using the SEC-01 Argon2id minimum profile."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher(
            time_cost=3,
            memory_cost=65536,
            parallelism=1,
            type=Type.ID,
        )

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)


class SecureBootstrapSecretGenerator:
    """Generates a high-entropy secret whose raw form is never persisted."""

    def generate(self) -> str:
        return secrets.token_urlsafe(32)


class TenantProvisioningRejectedError(Exception):
    """Neutral provisioning refusal for a malformed or already allocated tenant slug."""

    def __init__(self) -> None:
        super().__init__("TENANT_PROVISIONING_REJECTED")


class BootstrapTokenRejectedError(Exception):
    """Neutral refusal for absent, expired, cross-tenant or consumed bootstrap secrets."""

    def __init__(self) -> None:
        super().__init__("BOOTSTRAP_TOKEN_REJECTED")


class BootstrapCompletionRejectedError(Exception):
    """Neutral refusal for a bootstrap completion that cannot create a patron safely."""

    def __init__(self) -> None:
        super().__init__("BOOTSTRAP_COMPLETION_REJECTED")


@dataclass(frozen=True, slots=True)
class TenantProvisioningResult:
    """Local-installation result; the raw secret must be displayed only once."""

    tenant_id: UUID
    bootstrap_secret: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class FirstPatronBootstrapResult:
    """Persistent references returned after a completed first-patron bootstrap."""

    tenant_id: UUID
    identity_id: UUID
    membership_id: UUID


class TenantBootstrapService:
    """Creates a tenant token then atomically establishes its first active patron."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        password_hasher: PasswordCredentialHasher,
        bootstrap_secret_generator: BootstrapSecretGenerator,
        clock: Clock,
    ) -> None:
        self._session_factory = session_factory
        self._password_hasher = password_hasher
        self._bootstrap_secret_generator = bootstrap_secret_generator
        self._clock = clock

    def provision_tenant(self, *, slug: str) -> TenantProvisioningResult:
        """Provision tenant and expiring token in one local-administration transaction."""
        normalized_slug = _normalize_slug(slug)
        if normalized_slug is None:
            raise TenantProvisioningRejectedError()
        now = self._now()
        try:
            with self._session_factory.begin() as session:
                existing_tenant = session.scalar(
                    sa.select(TenantRecord.id)
                    .where(TenantRecord.slug == normalized_slug)
                    .with_for_update()
                )
                if existing_tenant is not None:
                    raise TenantProvisioningRejectedError()
                raw_secret = self._bootstrap_secret_generator.generate()
                expires_at = now + _BOOTSTRAP_TOKEN_TTL
                tenant_id = uuid4()
                session.add(
                    TenantRecord(
                        id=tenant_id,
                        slug=normalized_slug,
                        lifecycle="ACTIVE",
                    )
                )
                session.add(
                    TenantBootstrapTokenRecord(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        token_hash=_hash_secret(raw_secret),
                        issued_at=now,
                        expires_at=expires_at,
                        consumed_at=None,
                    )
                )
        except TenantProvisioningRejectedError:
            raise
        except IntegrityError as error:
            raise TenantProvisioningRejectedError() from error
        return TenantProvisioningResult(
            tenant_id=tenant_id,
            bootstrap_secret=raw_secret,
            expires_at=expires_at,
        )

    def complete_first_patron(
        self,
        *,
        tenant_id: UUID,
        bootstrap_secret: str,
        email: str,
        password: str,
    ) -> FirstPatronBootstrapResult:
        """Consume token while creating tenant identity, credential and active patron membership."""
        normalized_email = email.strip().lower()
        if not normalized_email or len(normalized_email) > 320 or len(password) < 14:
            raise BootstrapCompletionRejectedError()
        now = self._now()
        bootstrap_hash = _hash_secret(bootstrap_secret)
        identity_id = uuid4()
        membership_id = uuid4()
        try:
            with self._session_factory.begin() as session:
                token = session.scalar(
                    sa.select(TenantBootstrapTokenRecord)
                    .where(
                        TenantBootstrapTokenRecord.tenant_id == tenant_id,
                        TenantBootstrapTokenRecord.token_hash == bootstrap_hash,
                    )
                    .with_for_update()
                )
                tenant = session.scalar(
                    sa.select(TenantRecord)
                    .where(TenantRecord.id == tenant_id, TenantRecord.lifecycle == "ACTIVE")
                    .with_for_update()
                )
                if (
                    token is None
                    or tenant is None
                    or token.consumed_at is not None
                    or token.expires_at <= now
                ):
                    raise BootstrapTokenRejectedError()

                active_patron_exists = session.scalar(
                    sa.select(sa.exists().where(
                        TenantMembershipRecord.tenant_id == tenant_id,
                        TenantMembershipRecord.role == "PATRON_ADMIN",
                        TenantMembershipRecord.state == "ACTIVE",
                    ))
                )
                if active_patron_exists:
                    raise BootstrapTokenRejectedError()

                password_hash = self._password_hasher.hash(password)
                if not password_hash.startswith("$argon2id$"):
                    raise BootstrapCompletionRejectedError()
                session.add(
                    IdentityRecord(
                        id=identity_id,
                        email_normalized=normalized_email,
                        lifecycle="ACTIVE",
                        email_verified_at=None,
                    )
                )
                session.add(
                    PasswordCredentialRecord(
                        id=uuid4(),
                        identity_id=identity_id,
                        password_hash=password_hash,
                        algorithm="ARGON2ID",
                        parameters_version=1,
                        changed_at=now,
                        must_change=False,
                    )
                )
                session.add(
                    TenantMembershipRecord(
                        id=membership_id,
                        tenant_id=tenant_id,
                        identity_id=identity_id,
                        role="PATRON_ADMIN",
                        state="ACTIVE",
                        activated_at=now,
                        revoked_at=None,
                    )
                )
                token.consumed_at = now
        except BootstrapTokenRejectedError:
            raise
        except BootstrapCompletionRejectedError:
            raise
        except IntegrityError as error:
            raise BootstrapCompletionRejectedError() from error

        return FirstPatronBootstrapResult(
            tenant_id=tenant_id,
            identity_id=identity_id,
            membership_id=membership_id,
        )

    def _now(self) -> datetime:
        current = self._clock.now()
        if current.tzinfo is None:
            raise ValueError("bootstrap clock must return a timezone-aware timestamp")
        return current.astimezone(UTC)


def _normalize_slug(value: str) -> str | None:
    normalized = value.strip().lower()
    return normalized if _SLUG_PATTERN.fullmatch(normalized) is not None else None


def _hash_secret(raw_secret: str) -> str:
    return hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()

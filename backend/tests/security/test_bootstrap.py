from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from app.platform.persistence.models import TenantRecord
from app.platform.security.bootstrap import (
    BootstrapCompletionRejectedError,
    BootstrapTokenRejectedError,
    TenantBootstrapService,
    TenantProvisioningRejectedError,
)
from app.platform.security.models import (
    IdentityRecord,
    PasswordCredentialRecord,
    TenantBootstrapTokenRecord,
    TenantMembershipRecord,
)
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def isolate_bootstrap_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FixedSecret:
    def __init__(self, value: str = "boot" + "strap-token") -> None:
        self.value = value

    def generate(self) -> str:
        return self.value


class FixedHasher:
    def __init__(self, value: str = "$argon2id$v=19$test-hash") -> None:
        self.value = value

    def hash(self, password: str) -> str:
        return self.value


def _service(
    session_factory: sessionmaker[Session],
    *,
    secret: str = "boot" + "strap-token",
    password_hash: str = "$argon2id$v=19$test-hash",
) -> TenantBootstrapService:
    return TenantBootstrapService(
        session_factory=session_factory,
        password_hasher=FixedHasher(password_hash),
        bootstrap_secret_generator=FixedSecret(secret),
        clock=FixedClock(),
    )


@pytest.mark.db
@pytest.mark.security
def test_provision_tenant_normalizes_slug_and_hashes_one_time_secret(
    session_factory: sessionmaker[Session],
) -> None:
    service = _service(session_factory)

    result = service.provision_tenant(slug="  Acme-BTP  ")

    assert result.bootstrap_secret == "boot" + "strap-token"  # pragma: allowlist secret
    assert result.expires_at == NOW + timedelta(hours=1)
    with session_factory() as session:
        tenant = session.get(TenantRecord, result.tenant_id)
        token = session.scalar(
            sa.select(TenantBootstrapTokenRecord).where(
                TenantBootstrapTokenRecord.tenant_id == result.tenant_id
            )
        )
        assert tenant is not None and tenant.slug == "acme-btp"
        assert token is not None
        assert token.token_hash != result.bootstrap_secret
        assert token.consumed_at is None


@pytest.mark.db
@pytest.mark.security
@pytest.mark.parametrize("slug", ["", "x", "contains space", "UPPER_underscore", "a" * 121])
def test_provision_tenant_rejects_invalid_slug(
    session_factory: sessionmaker[Session], slug: str
) -> None:
    with pytest.raises(TenantProvisioningRejectedError, match="TENANT_PROVISIONING_REJECTED"):
        _service(session_factory).provision_tenant(slug=slug)


@pytest.mark.db
@pytest.mark.security
def test_provision_tenant_rejects_duplicate_slug(
    session_factory: sessionmaker[Session],
) -> None:
    service = _service(session_factory)
    service.provision_tenant(slug="acme-btp")

    with pytest.raises(TenantProvisioningRejectedError):
        service.provision_tenant(slug=" ACME-BTP ")


@pytest.mark.db
@pytest.mark.security
def test_complete_first_patron_persists_identity_credential_and_membership(
    session_factory: sessionmaker[Session],
) -> None:
    service = _service(session_factory)
    provisioned = service.provision_tenant(slug="acme-btp")

    result = service.complete_first_patron(
        tenant_id=provisioned.tenant_id,
        bootstrap_secret=provisioned.bootstrap_secret,
        email="  Patron@Example.TEST ",
        password="secure-" + "value-14",  # pragma: allowlist secret
    )

    with session_factory() as session:
        identity = session.get(IdentityRecord, result.identity_id)
        credential = session.scalar(
            sa.select(PasswordCredentialRecord).where(
                PasswordCredentialRecord.identity_id == result.identity_id
            )
        )
        membership = session.get(TenantMembershipRecord, result.membership_id)
        token = session.scalar(
            sa.select(TenantBootstrapTokenRecord).where(
                TenantBootstrapTokenRecord.tenant_id == result.tenant_id
            )
        )
        assert identity is not None and identity.email_normalized == "patron@example.test"
        assert credential is not None and credential.password_hash.startswith("$argon2id$")
        assert membership is not None and membership.role == "PATRON_ADMIN"
        assert token is not None and token.consumed_at == NOW


@pytest.mark.db
@pytest.mark.security
def test_complete_first_patron_rejects_invalid_or_expired_tokens(
    session_factory: sessionmaker[Session],
) -> None:
    service = _service(session_factory)
    provisioned = service.provision_tenant(slug="acme-btp")

    with pytest.raises(BootstrapCompletionRejectedError):
        service.complete_first_patron(
            tenant_id=provisioned.tenant_id,
            bootstrap_secret=provisioned.bootstrap_secret,
            email="",
            password="short",  # pragma: allowlist secret
        )
    with pytest.raises(BootstrapTokenRejectedError):
        service.complete_first_patron(
            tenant_id=provisioned.tenant_id,
            bootstrap_secret="wrong-" + "token",  # pragma: allowlist secret
            email="patron@example.test",
            password="secure-" + "value-14",  # pragma: allowlist secret
        )

    with session_factory.begin() as session:
        token = session.scalar(
            sa.select(TenantBootstrapTokenRecord).where(
                TenantBootstrapTokenRecord.tenant_id == provisioned.tenant_id
            )
        )
        assert token is not None
        token.issued_at = NOW - timedelta(hours=2)
        token.expires_at = NOW - timedelta(seconds=1)

    with pytest.raises(BootstrapTokenRejectedError):
        service.complete_first_patron(
            tenant_id=provisioned.tenant_id,
            bootstrap_secret=provisioned.bootstrap_secret,
            email="patron@example.test",
            password="secure-" + "value-14",  # pragma: allowlist secret
        )


@pytest.mark.db
@pytest.mark.security
def test_complete_first_patron_rejects_non_argon_hash_and_reuse(
    session_factory: sessionmaker[Session],
) -> None:
    bad_service = _service(session_factory, password_hash="bcrypt-hash")
    provisioned = bad_service.provision_tenant(slug="bad-hash")

    with pytest.raises(BootstrapCompletionRejectedError):
        bad_service.complete_first_patron(
            tenant_id=provisioned.tenant_id,
            bootstrap_secret=provisioned.bootstrap_secret,
            email="patron@example.test",
            password="secure-" + "value-14",  # pragma: allowlist secret
        )

    good_service = _service(session_factory, secret="second-bootstrap-secret")
    provisioned = good_service.provision_tenant(slug="reusable-token")
    good_service.complete_first_patron(
        tenant_id=provisioned.tenant_id,
        bootstrap_secret=provisioned.bootstrap_secret,
        email="patron@example.test",
        password="secure-" + "value-14",  # pragma: allowlist secret
    )
    with pytest.raises(BootstrapTokenRejectedError):
        good_service.complete_first_patron(
            tenant_id=provisioned.tenant_id,
            bootstrap_secret=provisioned.bootstrap_secret,
            email="second@example.test",
            password="secure-" + "value-14",  # pragma: allowlist secret
        )

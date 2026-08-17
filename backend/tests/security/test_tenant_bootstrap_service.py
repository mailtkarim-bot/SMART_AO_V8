from __future__ import annotations

import hashlib
from collections import deque
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from app.platform.persistence.models import TenantRecord
from app.platform.security.bootstrap import (
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

FIXED_NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


class FixedClock:
    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class SequenceSecretGenerator:
    def __init__(self, *values: str) -> None:
        self._values = deque(values)

    def generate(self) -> str:
        return self._values.popleft()


class StubPasswordHasher:
    def hash(self, password: str) -> str:
        return f"$argon2id$bootstrap-{password}"


class FailingPasswordHasher:
    def hash(self, password: str) -> str:
        del password
        raise RuntimeError("simulated password hashing failure")






@pytest.fixture(autouse=True)
def isolate_bootstrap_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _service(
    session_factory: sessionmaker[Session],
    *,
    clock: FixedClock | None = None,
    password_hasher: StubPasswordHasher | FailingPasswordHasher | None = None,
) -> TenantBootstrapService:
    return TenantBootstrapService(
        session_factory=session_factory,
        password_hasher=password_hasher or StubPasswordHasher(),
        bootstrap_secret_generator=SequenceSecretGenerator(
            "bootstrap-raw-secret",
            "bootstrap-raw-secret-2",
            "bootstrap-raw-secret-3",
        ),
        clock=clock or FixedClock(),
    )


def _token_hash(raw_secret: str) -> str:
    return hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()


@pytest.mark.db
@pytest.mark.security
def test_provision_tenant_creates_only_a_hashed_expiring_bootstrap_secret(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    result = _service(session_factory).provision_tenant(slug="entreprise-dupont")

    assert result.bootstrap_secret == "bootstrap-raw-secret"
    assert result.expires_at == FIXED_NOW + timedelta(hours=1)
    with Session(database_engine) as session:
        tenant = session.get(TenantRecord, result.tenant_id)
        token = session.scalar(
            sa.select(TenantBootstrapTokenRecord).where(
                TenantBootstrapTokenRecord.tenant_id == result.tenant_id
            )
        )

        assert tenant is not None
        assert tenant.slug == "entreprise-dupont"
        assert tenant.lifecycle == "ACTIVE"
        assert token is not None
        assert token.token_hash == _token_hash(result.bootstrap_secret)
        assert token.token_hash != result.bootstrap_secret
        assert token.issued_at == FIXED_NOW
        assert token.expires_at == result.expires_at
        assert token.consumed_at is None


@pytest.mark.db
@pytest.mark.security
def test_complete_bootstrap_creates_active_patron_and_consumes_token_atomically(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    service = _service(session_factory)
    provisioned = service.provision_tenant(slug="entreprise-dupont")

    completed = service.complete_first_patron(
        tenant_id=provisioned.tenant_id,
        bootstrap_secret=provisioned.bootstrap_secret,
        email="Patron@Example.Test",
        password="A-Very-Long-Initial-Password",
    )

    assert completed.tenant_id == provisioned.tenant_id
    with Session(database_engine) as session:
        identity = session.get(IdentityRecord, completed.identity_id)
        membership = session.get(TenantMembershipRecord, completed.membership_id)
        credential = session.scalar(
            sa.select(PasswordCredentialRecord).where(
                PasswordCredentialRecord.identity_id == completed.identity_id
            )
        )
        token = session.scalar(
            sa.select(TenantBootstrapTokenRecord).where(
                TenantBootstrapTokenRecord.tenant_id == provisioned.tenant_id
            )
        )

        assert identity is not None
        assert identity.email_normalized == "patron@example.test"
        assert identity.lifecycle == "ACTIVE"
        assert membership is not None
        assert membership.tenant_id == provisioned.tenant_id
        assert membership.identity_id == completed.identity_id
        assert membership.role == "PATRON_ADMIN"
        assert membership.state == "ACTIVE"
        assert membership.activated_at == FIXED_NOW
        assert credential is not None
        assert credential.algorithm == "ARGON2ID"
        assert credential.password_hash.startswith("$argon2id$")
        assert credential.must_change is False
        assert token is not None
        assert token.consumed_at == FIXED_NOW


@pytest.mark.db
@pytest.mark.security
def test_consumed_bootstrap_secret_is_never_reusable(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    service = _service(session_factory)
    provisioned = service.provision_tenant(slug="entreprise-dupont")
    service.complete_first_patron(
        tenant_id=provisioned.tenant_id,
        bootstrap_secret=provisioned.bootstrap_secret,
        email="patron@example.test",
        password="A-Very-Long-Initial-Password",
    )

    with pytest.raises(BootstrapTokenRejectedError) as captured:
        service.complete_first_patron(
            tenant_id=provisioned.tenant_id,
            bootstrap_secret=provisioned.bootstrap_secret,
            email="another@example.test",
            password="A-Very-Long-Initial-Password",
        )

    assert str(captured.value) == "BOOTSTRAP_TOKEN_REJECTED"
    with Session(database_engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(IdentityRecord)) == 1
        assert session.scalar(
            sa.select(sa.func.count())
            .select_from(TenantMembershipRecord)
            .where(TenantMembershipRecord.role == "PATRON_ADMIN")
        ) == 1


@pytest.mark.db
@pytest.mark.security
def test_bootstrap_token_is_rejected_for_another_tenant_without_disclosure(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    service = _service(session_factory)
    source = service.provision_tenant(slug="entreprise-source")
    target = service.provision_tenant(slug="entreprise-target")

    with pytest.raises(BootstrapTokenRejectedError) as captured:
        service.complete_first_patron(
            tenant_id=target.tenant_id,
            bootstrap_secret=source.bootstrap_secret,
            email="patron@example.test",
            password="A-Very-Long-Initial-Password",
        )

    assert str(captured.value) == "BOOTSTRAP_TOKEN_REJECTED"
    with Session(database_engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(IdentityRecord)) == 0
        target_token = session.scalar(
            sa.select(TenantBootstrapTokenRecord).where(
                TenantBootstrapTokenRecord.tenant_id == target.tenant_id
            )
        )
        assert target_token is not None
        assert target_token.consumed_at is None


@pytest.mark.db
@pytest.mark.security
def test_expired_bootstrap_secret_is_rejected_without_creating_patron(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    provisioner = _service(session_factory)
    provisioned = provisioner.provision_tenant(slug="entreprise-dupont")
    expired_service = _service(
        session_factory,
        clock=FixedClock(FIXED_NOW + timedelta(hours=2)),
    )

    with pytest.raises(BootstrapTokenRejectedError):
        expired_service.complete_first_patron(
            tenant_id=provisioned.tenant_id,
            bootstrap_secret=provisioned.bootstrap_secret,
            email="patron@example.test",
            password="A-Very-Long-Initial-Password",
        )

    with Session(database_engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(IdentityRecord)) == 0
        token = session.scalar(
            sa.select(TenantBootstrapTokenRecord).where(
                TenantBootstrapTokenRecord.tenant_id == provisioned.tenant_id
            )
        )
        assert token is not None
        assert token.consumed_at is None


@pytest.mark.db
@pytest.mark.security
def test_bootstrap_rolls_back_identity_membership_and_token_consumption_on_failure(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    provisioner = _service(session_factory)
    provisioned = provisioner.provision_tenant(slug="entreprise-dupont")
    failing_service = _service(session_factory, password_hasher=FailingPasswordHasher())

    with pytest.raises(RuntimeError, match="simulated password hashing failure"):
        failing_service.complete_first_patron(
            tenant_id=provisioned.tenant_id,
            bootstrap_secret=provisioned.bootstrap_secret,
            email="patron@example.test",
            password="A-Very-Long-Initial-Password",
        )

    with Session(database_engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(IdentityRecord)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(TenantMembershipRecord)) == 0
        token = session.scalar(
            sa.select(TenantBootstrapTokenRecord).where(
                TenantBootstrapTokenRecord.tenant_id == provisioned.tenant_id
            )
        )
        assert token is not None
        assert token.consumed_at is None


@pytest.mark.db
@pytest.mark.security
def test_tenant_slug_cannot_be_provisioned_twice(
    session_factory: sessionmaker[Session],
) -> None:
    service = _service(session_factory)
    service.provision_tenant(slug="entreprise-dupont")

    with pytest.raises(TenantProvisioningRejectedError) as captured:
        service.provision_tenant(slug="entreprise-dupont")

    assert str(captured.value) == "TENANT_PROVISIONING_REJECTED"

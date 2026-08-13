from __future__ import annotations

import hashlib
import os
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.platform.security.authentication import (
    Argon2idPasswordVerifier,
    AuthenticationService,
    InvalidCredentialsError,
    RefreshRejectedError,
)
from app.platform.security.models import (
    AuthSessionRecord,
    IdentityRecord,
    PasswordCredentialRecord,
    RefreshTokenFamilyRecord,
    RefreshTokenRecord,
    TenantMembershipRecord,
)
from argon2 import PasswordHasher, Type
from sqlalchemy.orm import Session, sessionmaker

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = os.getenv(
    "SMART_AO_TEST_DATABASE_URL",
    "postgresql+psycopg://smart_ao:smart_ao@127.0.0.1:5432/smart_ao",
)
FIXED_NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return FIXED_NOW


class StubPasswordVerifier:
    def verify(self, *, password_hash: str, password: str) -> bool:
        return password_hash == "$argon2id$fixture" and password == "Correct#Pass123"


class SequenceTokenGenerator:
    def __init__(self, *tokens: str) -> None:
        self._tokens = deque(tokens)

    def generate(self) -> str:
        return self._tokens.popleft()


@pytest.fixture(scope="module")
def database_engine() -> sa.Engine:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(config, "head")
    engine = sa.create_engine(DATABASE_URL)
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(config, "base")


@pytest.fixture
def session_factory(database_engine: sa.Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=database_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def isolate_authentication_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants CASCADE"))


def _insert_tenant(engine: sa.Engine) -> UUID:
    tenant_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            sa.text("INSERT INTO tenants (id, slug, lifecycle) VALUES (:id, :slug, 'ACTIVE')"),
            {"id": tenant_id, "slug": f"tenant-{tenant_id}"},
        )
    return tenant_id


def _active_identity_with_membership(
    engine: sa.Engine,
    *,
    tenant_id: UUID,
) -> tuple[UUID, UUID, str]:
    identity_id = uuid4()
    membership_id = uuid4()
    email = f"patron-{identity_id}@example.test"
    with engine.begin() as connection:
        connection.execute(
            sa.insert(IdentityRecord).values(
                id=identity_id,
                email_normalized=email,
                lifecycle="ACTIVE",
                email_verified_at=FIXED_NOW,
            )
        )
        connection.execute(
            sa.insert(PasswordCredentialRecord).values(
                id=uuid4(),
                identity_id=identity_id,
                password_hash="$argon2id$fixture",
                algorithm="ARGON2ID",
                parameters_version=1,
                changed_at=FIXED_NOW,
                must_change=False,
            )
        )
        connection.execute(
            sa.insert(TenantMembershipRecord).values(
                id=membership_id,
                tenant_id=tenant_id,
                identity_id=identity_id,
                role="PATRON_ADMIN",
                state="ACTIVE",
                activated_at=FIXED_NOW,
                revoked_at=None,
            )
        )
    return identity_id, membership_id, email


def _service(
    session_factory: sessionmaker[Session],
    *tokens: str,
) -> AuthenticationService:
    return AuthenticationService(
        session_factory=session_factory,
        password_verifier=StubPasswordVerifier(),
        token_generator=SequenceTokenGenerator(*tokens),
        clock=FixedClock(),
    )


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@pytest.mark.db
@pytest.mark.security
def test_login_creates_session_family_and_hash_only_refresh_token_atomically(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    identity_id, membership_id, email = _active_identity_with_membership(
        database_engine,
        tenant_id=tenant_id,
    )

    result = _service(session_factory, "raw-refresh-1").login(
        email=email.upper(),
        password="Correct#Pass123",
        tenant_id=tenant_id,
    )

    assert result.identity_id == identity_id
    assert result.membership_id == membership_id
    assert result.refresh_token == "raw-refresh-1"
    assert result.session_expires_at == FIXED_NOW + timedelta(hours=8)
    assert result.session_absolute_expires_at == FIXED_NOW + timedelta(hours=12)
    with Session(database_engine) as session:
        auth_session = session.get(AuthSessionRecord, result.session_id)
        family = session.get(RefreshTokenFamilyRecord, result.refresh_family_id)
        refresh = session.scalar(
            sa.select(RefreshTokenRecord).where(
                RefreshTokenRecord.family_id == result.refresh_family_id
            )
        )

        assert auth_session is not None
        assert auth_session.tenant_id == tenant_id
        assert auth_session.membership_id == membership_id
        assert auth_session.identity_id == identity_id
        assert auth_session.state == "ACTIVE"
        assert auth_session.auth_strength == "PASSWORD"
        assert auth_session.token_version == 1
        assert auth_session.absolute_expires_at == FIXED_NOW + timedelta(hours=12)
        assert family is not None
        assert family.session_id == result.session_id
        assert family.state == "ACTIVE"
        assert refresh is not None
        assert refresh.state == "ACTIVE"
        assert refresh.token_hash == _token_hash("raw-refresh-1")
        assert refresh.token_hash != result.refresh_token
        assert refresh.parent_token_id is None


@pytest.mark.db
@pytest.mark.security
def test_login_refuses_unknown_credentials_neutrally_without_creating_session(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)

    with pytest.raises(InvalidCredentialsError) as captured:
        _service(session_factory, "unused").login(
            email="unknown@example.test",
            password="Wrong#Pass123",
            tenant_id=tenant_id,
        )

    assert str(captured.value) == "INVALID_CREDENTIALS"
    with Session(database_engine) as session:
        assert session.scalar(
            sa.select(sa.func.count())
            .select_from(AuthSessionRecord)
            .where(AuthSessionRecord.tenant_id == tenant_id)
        ) == 0
        assert session.scalar(
            sa.select(sa.func.count())
            .select_from(RefreshTokenRecord)
            .where(RefreshTokenRecord.tenant_id == tenant_id)
        ) == 0


@pytest.mark.db
@pytest.mark.security
def test_login_refuses_inactive_membership_without_creating_session(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    identity_id, membership_id, email = _active_identity_with_membership(
        database_engine,
        tenant_id=tenant_id,
    )
    with database_engine.begin() as connection:
        connection.execute(
            sa.update(TenantMembershipRecord)
            .where(TenantMembershipRecord.id == membership_id)
            .values(state="SUSPENDED")
        )

    with pytest.raises(InvalidCredentialsError):
        _service(session_factory, "unused").login(
            email=email,
            password="Correct#Pass123",
            tenant_id=tenant_id,
        )

    with Session(database_engine) as session:
        assert session.scalar(
            sa.select(sa.func.count())
            .select_from(AuthSessionRecord)
            .where(AuthSessionRecord.identity_id == identity_id)
        ) == 0


@pytest.mark.db
@pytest.mark.security
def test_refresh_rotates_once_and_preserves_a_single_active_token(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    _, _, email = _active_identity_with_membership(database_engine, tenant_id=tenant_id)
    service = _service(session_factory, "raw-refresh-1", "raw-refresh-2")
    initial = service.login(
        email=email,
        password="Correct#Pass123",
        tenant_id=tenant_id,
    )

    rotated = service.refresh(refresh_token=initial.refresh_token)

    assert rotated.session_id == initial.session_id
    assert rotated.refresh_family_id == initial.refresh_family_id
    assert rotated.refresh_token == "raw-refresh-2"
    with Session(database_engine) as session:
        tokens = session.scalars(
            sa.select(RefreshTokenRecord)
            .where(RefreshTokenRecord.family_id == initial.refresh_family_id)
            .order_by(RefreshTokenRecord.issued_at, RefreshTokenRecord.id)
        ).all()

        assert len(tokens) == 2
        old_token = next(token for token in tokens if token.id != rotated.refresh_token_id)
        new_token = next(token for token in tokens if token.id == rotated.refresh_token_id)
        assert old_token.state == "ROTATED"
        assert old_token.consumed_at == FIXED_NOW
        assert new_token.state == "ACTIVE"
        assert new_token.parent_token_id == old_token.id
        assert new_token.token_hash == _token_hash("raw-refresh-2")


@pytest.mark.db
@pytest.mark.security
def test_refresh_replay_compromises_family_and_revokes_session(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    _, _, email = _active_identity_with_membership(database_engine, tenant_id=tenant_id)
    service = _service(session_factory, "raw-refresh-1", "raw-refresh-2")
    initial = service.login(
        email=email,
        password="Correct#Pass123",
        tenant_id=tenant_id,
    )
    service.refresh(refresh_token=initial.refresh_token)

    with pytest.raises(RefreshRejectedError) as captured:
        service.refresh(refresh_token=initial.refresh_token)

    assert str(captured.value) == "REFRESH_REJECTED"
    with Session(database_engine) as session:
        auth_session = session.get(AuthSessionRecord, initial.session_id)
        family = session.get(RefreshTokenFamilyRecord, initial.refresh_family_id)
        active_tokens = session.scalar(
            sa.select(sa.func.count())
            .select_from(RefreshTokenRecord)
            .where(
                RefreshTokenRecord.family_id == initial.refresh_family_id,
                RefreshTokenRecord.state == "ACTIVE",
            )
        )

        assert auth_session is not None
        assert auth_session.state == "REVOKED"
        assert auth_session.revoke_reason == "REFRESH_REPLAY"
        assert auth_session.token_version == 2
        assert family is not None
        assert family.state == "COMPROMISED"
        assert family.revoke_reason == "REFRESH_REPLAY"
        assert active_tokens == 0


@pytest.mark.db
@pytest.mark.security
def test_logout_revokes_session_family_and_active_refresh_token(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    _, _, email = _active_identity_with_membership(database_engine, tenant_id=tenant_id)
    service = _service(session_factory, "raw-refresh-1")
    login = service.login(
        email=email,
        password="Correct#Pass123",
        tenant_id=tenant_id,
    )

    assert service.logout(session_id=login.session_id) is True
    assert service.logout(session_id=login.session_id) is False
    with Session(database_engine) as session:
        auth_session = session.get(AuthSessionRecord, login.session_id)
        family = session.get(RefreshTokenFamilyRecord, login.refresh_family_id)
        refresh = session.get(RefreshTokenRecord, login.refresh_token_id)

        assert auth_session is not None
        assert auth_session.state == "REVOKED"
        assert auth_session.revoke_reason == "LOGOUT"
        assert auth_session.token_version == 2
        assert family is not None
        assert family.state == "REVOKED"
        assert family.revoke_reason == "LOGOUT"
        assert refresh is not None
        assert refresh.state == "REVOKED"
        assert refresh.revoked_at == FIXED_NOW

    with pytest.raises(RefreshRejectedError):
        service.refresh(refresh_token=login.refresh_token)


@pytest.mark.db
@pytest.mark.security
def test_refresh_after_membership_suspension_revokes_the_session_lineage(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    _, membership_id, email = _active_identity_with_membership(database_engine, tenant_id=tenant_id)
    service = _service(session_factory, "raw-refresh-1")
    login = service.login(
        email=email,
        password="Correct#Pass123",
        tenant_id=tenant_id,
    )
    with database_engine.begin() as connection:
        connection.execute(
            sa.update(TenantMembershipRecord)
            .where(TenantMembershipRecord.id == membership_id)
            .values(state="SUSPENDED")
        )

    with pytest.raises(RefreshRejectedError):
        service.refresh(refresh_token=login.refresh_token)

    with Session(database_engine) as session:
        auth_session = session.get(AuthSessionRecord, login.session_id)
        family = session.get(RefreshTokenFamilyRecord, login.refresh_family_id)
        refresh = session.get(RefreshTokenRecord, login.refresh_token_id)

        assert auth_session is not None
        assert auth_session.state == "REVOKED"
        assert auth_session.revoke_reason == "AUTH_CONTEXT_INVALID"
        assert family is not None
        assert family.state == "REVOKED"
        assert refresh is not None
        assert refresh.state == "REVOKED"


@pytest.mark.security
def test_argon2id_password_verifier_accepts_only_matching_argon2id_credentials() -> None:
    encoded = PasswordHasher(type=Type.ID).hash("Correct#Pass123")
    verifier = Argon2idPasswordVerifier()

    assert verifier.verify(password_hash=encoded, password="Correct#Pass123") is True
    assert verifier.verify(password_hash=encoded, password="Wrong#Pass123") is False
    assert verifier.verify(password_hash="$argon2i$fixture", password="Correct#Pass123") is False

"""API contract tests for the server-filtered assigned Case collection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.bootstrap.application import AppRuntime, create_app
from app.interfaces.http.routes.authentication import AuthenticationHttpRuntime
from app.modules.case.infrastructure.models.case import CaseRecord
from app.platform.security.authentication import AuthenticationService
from app.platform.security.models import (
    AuthSessionRecord,
    CaseAssignmentRecord,
    IdentityRecord,
    TenantMembershipRecord,
)
from app.platform.security.tokens import JwtAccessTokenCodec
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = (
    "postgresql+psycopg://smart_ao:smart_ao@127.0.0.1:5432/smart_ao"  # pragma: allowlist secret
)
NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class UnusedPasswordVerifier:
    def verify(self, *, password_hash: str, password: str) -> bool:
        return False


class UnusedTokenGenerator:
    def generate(self) -> str:
        return "unused-token"


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
def isolate_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_principal(
    engine: sa.Engine,
    *,
    role: str,
    tenant_id: UUID | None = None,
) -> tuple[UUID, UUID, UUID]:
    tenant_id = tenant_id or uuid4()
    identity_id, membership_id, session_id = uuid4(), uuid4(), uuid4()
    with engine.begin() as connection:
        connection.execute(
            sa.text("INSERT INTO tenants (id, slug, lifecycle) VALUES (:id, :slug, 'ACTIVE')"),
            {"id": tenant_id, "slug": f"tenant-{tenant_id.hex[:12]}"},
        )
        connection.execute(
            sa.insert(IdentityRecord).values(
                id=identity_id,
                email_normalized=f"user-{identity_id}@example.test",
                lifecycle="ACTIVE",
                email_verified_at=NOW,
            )
        )
        connection.execute(
            sa.insert(TenantMembershipRecord).values(
                id=membership_id,
                tenant_id=tenant_id,
                identity_id=identity_id,
                role=role,
                state="ACTIVE",
                activated_at=NOW,
                revoked_at=None,
            )
        )
        connection.execute(
            sa.insert(AuthSessionRecord).values(
                id=session_id,
                tenant_id=tenant_id,
                membership_id=membership_id,
                identity_id=identity_id,
                state="ACTIVE",
                auth_strength="PASSWORD",
                token_version=1,
                issued_at=NOW,
                last_seen_at=NOW,
                expires_at=NOW + timedelta(hours=8),
                absolute_expires_at=NOW + timedelta(hours=12),
                mfa_verified_at=None,
                revoked_at=None,
                revoke_reason=None,
            )
        )
    return tenant_id, identity_id, membership_id, session_id


def _seed_case(
    session_factory: sessionmaker[Session], *, tenant_id: UUID, lifecycle: str = "ACTIVE"
) -> UUID:
    case_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            CaseRecord(
                id=case_id,
                tenant_id=tenant_id,
                aggregate_revision=1,
                functional_identity_hash=uuid4().hex + uuid4().hex,
                title=f"Affaire {case_id.hex[:8]}",
                object_description="Ne doit jamais sortir dans la projection.",
                business_origin="MANUAL",
                origin_reference_id=None,
                origin_rationale="Cas de test contrôlé",
                consultation_id=None,
                scope_kind="CUSTOM",
                scope_json={"forbidden": "scope"},
                scope_fingerprint="a" * 64,
                applicable_dce_version_id=None,
                lifecycle=lifecycle,
                commercial_stage="ANALYSIS",
                decision_readiness="NOT_ASSESSED",
                dce_freshness="NO_DCE",
                responsibility_status="UNASSIGNED",
                stopped_reason=None,
                stopped_at=None,
                archived_reason="test archive" if lifecycle == "ARCHIVED" else None,
                archived_at=NOW if lifecycle == "ARCHIVED" else None,
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
    return case_id


def _assign(
    session_factory: sessionmaker[Session],
    *,
    tenant_id: UUID,
    membership_id: UUID,
    case_id: UUID,
    actions: list[str],
) -> None:
    with session_factory.begin() as session:
        session.add(
            CaseAssignmentRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                membership_id=membership_id,
                case_id=case_id,
                state="ACTIVE",
                scope_actions_json=actions,
                scope_classifications_json=["INTERNAL_OPERATIONAL"],
                granted_by_membership_id=membership_id,
                granted_at=NOW,
                starts_at=NOW,
                ends_at=None,
                ended_at=None,
            )
        )


def _client(
    session_factory: sessionmaker[Session],
) -> tuple[TestClient, JwtAccessTokenCodec]:
    clock = FixedClock()
    tokens = JwtAccessTokenCodec(
        signing_key="test-only-signing-key-at-least-32-bytes",
        issuer="smart-ao-test",
        audience="smart-ao-web",
        clock=clock,
    )
    auth_runtime = AuthenticationHttpRuntime.create(
        authentication_service=AuthenticationService(
            session_factory=session_factory,
            password_verifier=UnusedPasswordVerifier(),
            token_generator=UnusedTokenGenerator(),
            clock=clock,
        ),
        session_factory=session_factory,
        access_tokens=tokens,
        csrf_token_generator=UnusedTokenGenerator(),
        clock=clock,
    )
    return (
        TestClient(
            create_app(
                runtime=AppRuntime.create(session_factory=session_factory),
                authentication_runtime=auth_runtime,
            ),
            base_url="https://smart-ao.test",
        ),
        tokens,
    )


def _headers(
    tokens: JwtAccessTokenCodec,
    *,
    identity_id: UUID,
    session_id: UUID,
) -> dict[str, str]:
    return {
        "Authorization": (
            "Bearer "
            f"{tokens.issue(identity_id=identity_id, session_id=session_id, token_version=1)}"
        )
    }


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_sees_all_non_archived_cases_of_own_tenant(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(
        database_engine, role="PATRON_ADMIN"
    )
    visible_case = _seed_case(session_factory, tenant_id=tenant_id)
    _seed_case(session_factory, tenant_id=tenant_id)
    _seed_case(session_factory, tenant_id=tenant_id, lifecycle="ARCHIVED")
    client, tokens = _client(session_factory)

    response = client.get(
        "/api/v1/cases/assigned",
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert visible_case in {UUID(item["case_id"]) for item in payload}
    assert len(payload) == 2


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_assigned_collaborator_sees_only_case_with_required_scope(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, membership_id, session_id = _seed_principal(
        database_engine, role="COLLABORATEUR"
    )
    assigned_case = _seed_case(session_factory, tenant_id=tenant_id)
    hidden_case = _seed_case(session_factory, tenant_id=tenant_id)
    _assign(
        session_factory,
        tenant_id=tenant_id,
        membership_id=membership_id,
        case_id=assigned_case,
        actions=["case.dce.read"],
    )
    client, tokens = _client(session_factory)

    response = client.get(
        "/api/v1/cases/assigned",
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 200
    assert [UUID(item["case_id"]) for item in response.json()] == [assigned_case]
    assert hidden_case not in {UUID(item["case_id"]) for item in response.json()}


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_collaborator_without_assignment_gets_empty_collection(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(
        database_engine, role="COLLABORATEUR"
    )
    _seed_case(session_factory, tenant_id=tenant_id)
    client, tokens = _client(session_factory)

    response = client.get(
        "/api/v1/cases/assigned",
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_collaborator_assignment_without_read_capability_is_filtered(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, membership_id, session_id = _seed_principal(
        database_engine, role="COLLABORATEUR"
    )
    case_id = _seed_case(session_factory, tenant_id=tenant_id)
    _assign(
        session_factory,
        tenant_id=tenant_id,
        membership_id=membership_id,
        case_id=case_id,
        actions=["dce.requirement.confirm"],
    )
    client, tokens = _client(session_factory)

    response = client.get(
        "/api/v1/cases/assigned",
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_collection_requires_bearer_authentication(
    session_factory: sessionmaker[Session],
) -> None:
    client, _ = _client(session_factory)

    response = client.get("/api/v1/cases/assigned")

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_cross_tenant_cases_are_neutral_and_not_returned(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    foreign_tenant = uuid4()
    _seed_principal(database_engine, role="PATRON_ADMIN", tenant_id=foreign_tenant)
    local_tenant, identity_id, _, session_id = _seed_principal(
        database_engine, role="PATRON_ADMIN"
    )
    foreign_case = _seed_case(session_factory, tenant_id=foreign_tenant)
    _seed_case(session_factory, tenant_id=local_tenant)
    client, tokens = _client(session_factory)

    response = client.get(
        "/api/v1/cases/assigned",
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 200
    assert foreign_case not in {UUID(item["case_id"]) for item in response.json()}
    assert len(response.json()) == 1


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_collection_is_a_closed_projection_without_forbidden_fields(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(
        database_engine, role="PATRON_ADMIN"
    )
    _seed_case(session_factory, tenant_id=tenant_id)
    client, tokens = _client(session_factory)

    response = client.get(
        "/api/v1/cases/assigned",
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 200
    assert set(response.json()[0]) == {
        "case_id",
        "work_label",
        "case_lifecycle",
        "commercial_stage",
        "dce_availability",
    }
    serialized = response.text
    for forbidden in (
        "tenant_id",
        "scope_json",
        "scope_fingerprint",
        "functional_identity_hash",
        "object_description",
        "price",
        "margin",
        "audit",
    ):
        assert forbidden not in serialized

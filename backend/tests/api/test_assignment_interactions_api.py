from __future__ import annotations

import os
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
    SecurityAuditEventRecord,
    TenantMembershipRecord,
)
from app.platform.security.tokens import JwtAccessTokenCodec
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = os.getenv("SMART_AO_TEST_DATABASE_URL") or (
    "postgresql+psycopg://"
    + "smart_ao"
    + ":"
    + "smart_ao"
    + "@127.0.0.1:5432/smart_ao"
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
        return "unused-refresh-token"


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
    role: str = "COLLABORATEUR",
    tenant_id: UUID | None = None,
) -> tuple[UUID, UUID, UUID, UUID]:
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


def _seed_case_and_assignment(
    session_factory: sessionmaker[Session],
    *,
    tenant_id: UUID,
    membership_id: UUID,
    scope_actions: list[str],
) -> tuple[UUID, UUID]:
    case_id, assignment_id = uuid4(), uuid4()
    with session_factory.begin() as session:
        session.add(
            CaseRecord(
                id=case_id,
                tenant_id=tenant_id,
                aggregate_revision=1,
                functional_identity_hash="a" * 64,
                title="Affaire HTTP Assignment",
                object_description=None,
                business_origin="MANUAL",
                origin_reference_id=None,
                origin_rationale="Test de façade HTTP",
                consultation_id=None,
                scope_kind="CUSTOM",
                scope_json={},
                scope_fingerprint="b" * 64,
                applicable_dce_version_id=None,
                lifecycle="ACTIVE",
                commercial_stage="ANALYSIS",
                decision_readiness="NOT_ASSESSED",
                dce_freshness="NO_DCE",
                responsibility_status="ASSIGNED",
                stopped_reason=None,
                stopped_at=None,
                archived_reason=None,
                archived_at=None,
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        session.flush()
        session.add(
            CaseAssignmentRecord(
                id=assignment_id,
                tenant_id=tenant_id,
                membership_id=membership_id,
                case_id=case_id,
                aggregate_revision=0,
                state="ACTIVE",
                scope_actions_json=scope_actions,
                scope_classifications_json=["INTERNAL_OPERATIONAL"],
                granted_by_membership_id=membership_id,
                granted_at=NOW,
                starts_at=NOW,
                ends_at=None,
                ended_at=None,
            )
        )
    return case_id, assignment_id


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


def _ack_payload() -> dict[str, str | int]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": 0,
        "note": "Affectation reçue.",
    }


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_assignment_acknowledgement_returns_closed_receipt_and_replays(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, membership_id, session_id = _seed_principal(database_engine)
    _, assignment_id = _seed_case_and_assignment(
        session_factory,
        tenant_id=tenant_id,
        membership_id=membership_id,
        scope_actions=["assignment.acknowledge"],
    )
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    payload = _ack_payload()

    first = client.post(
        f"/api/v1/assignments/{assignment_id}/acknowledgement",
        json=payload,
        headers=headers,
    )
    replay = client.post(
        f"/api/v1/assignments/{assignment_id}/acknowledgement",
        json=payload,
        headers=headers,
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["result_code"] == "ASSIGNMENT_ACKNOWLEDGED"
    assert replay.json()["replayed"] is True
    assert set(first.json()) == {
        "status",
        "command_id",
        "idempotency_key",
        "result_code",
        "aggregate_refs",
        "event_ids",
        "replayed",
    }
    assert first.json()["aggregate_refs"][0]["aggregate_revision"] == 1


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
@pytest.mark.parametrize(
    ("suffix", "scope_action", "payload", "result_code"),
    [
        (
            "clarification-requests",
            "assignment.clarify",
            {
                "command_id": str(uuid4()),
                "idempotency_key": str(uuid4()),
                "correlation_id": str(uuid4()),
                "expected_revision": 0,
                "clarification_kind": "SCOPE",
                "subject": "Périmètre du lot",
                "question": "Quel poste est prioritaire ?",
                "requested_scope": "Lot structure",
                "priority": "HIGH",
            },
            "ASSIGNMENT_CLARIFICATION_REQUESTED",
        ),
        (
            "unavailability-reports",
            "assignment.unavailability",
            {
                "command_id": str(uuid4()),
                "idempotency_key": str(uuid4()),
                "correlation_id": str(uuid4()),
                "expected_revision": 0,
                "reason_kind": "CAPACITY_CONFLICT",
                "reason": "Conflit de capacité déclaré.",
                "unavailable_from": "2026-08-15T12:00:00Z",
                "unavailable_until": "2026-08-17T12:00:00Z",
                "known_deadline_impact": True,
                "impact_note": "Le patron doit vérifier la remise.",
            },
            "ASSIGNMENT_UNAVAILABILITY_REPORTED",
        ),
    ],
)
def test_other_assignment_routes_dispatch_their_closed_command(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
    suffix: str,
    scope_action: str,
    payload: dict[str, object],
    result_code: str,
) -> None:
    tenant_id, identity_id, membership_id, session_id = _seed_principal(database_engine)
    _, assignment_id = _seed_case_and_assignment(
        session_factory,
        tenant_id=tenant_id,
        membership_id=membership_id,
        scope_actions=[scope_action],
    )
    client, tokens = _client(session_factory)

    response = client.post(
        f"/api/v1/assignments/{assignment_id}/{suffix}",
        json=payload,
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 201
    assert response.json()["result_code"] == result_code


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_assignment_idempotency_key_reuse_with_different_payload_is_409(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, membership_id, session_id = _seed_principal(database_engine)
    _, assignment_id = _seed_case_and_assignment(
        session_factory,
        tenant_id=tenant_id,
        membership_id=membership_id,
        scope_actions=["assignment.acknowledge"],
    )
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    payload = _ack_payload()
    first = client.post(
        f"/api/v1/assignments/{assignment_id}/acknowledgement",
        json=payload,
        headers=headers,
    )
    conflict_payload = {
        **payload,
        "command_id": str(uuid4()),
        "note": "Contenu différent avec la même clé.",
    }
    conflict = client.post(
        f"/api/v1/assignments/{assignment_id}/acknowledgement",
        json=conflict_payload,
        headers=headers,
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "IDEMPOTENCY_KEY_REUSED"}


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_assignment_scope_denial_is_403_and_audited(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, membership_id, session_id = _seed_principal(database_engine)
    _, assignment_id = _seed_case_and_assignment(
        session_factory,
        tenant_id=tenant_id,
        membership_id=membership_id,
        scope_actions=["case.dce.read"],
    )
    client, tokens = _client(session_factory)

    response = client.post(
        f"/api/v1/assignments/{assignment_id}/acknowledgement",
        json=_ack_payload(),
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "FORBIDDEN"}
    with session_factory() as session:
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord).where(
                SecurityAuditEventRecord.event_type == "AUTHZ_DENIED",
                SecurityAuditEventRecord.action == "assignment.acknowledge",
            )
        )
    assert audit is not None
    assert audit.reason_code == "AUTHORIZATION_DENIED"


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_assignment_foreign_or_missing_is_neutral_404_and_audited(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, membership_id, session_id = _seed_principal(database_engine)
    _, assignment_id = _seed_case_and_assignment(
        session_factory,
        tenant_id=tenant_id,
        membership_id=membership_id,
        scope_actions=["assignment.acknowledge"],
    )
    other_tenant, _, other_membership_id, _ = _seed_principal(database_engine)
    client, tokens = _client(session_factory)

    response = client.post(
        f"/api/v1/assignments/{assignment_id}/acknowledgement",
        json=_ack_payload(),
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )
    assert response.status_code == 201

    _, foreign_assignment = _seed_case_and_assignment(
        session_factory,
        tenant_id=other_tenant,
        membership_id=other_membership_id,
        scope_actions=["assignment.acknowledge"],
    )

    response = client.post(
        f"/api/v1/assignments/{foreign_assignment}/acknowledgement",
        json=_ack_payload(),
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "NOT_FOUND_OR_FORBIDDEN"}
    with session_factory() as session:
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord).where(
                SecurityAuditEventRecord.event_type == "AUTHZ_DENIED",
                SecurityAuditEventRecord.reason_code == "NOT_FOUND_OR_FORBIDDEN",
            )
        )
    assert audit is not None


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_assignment_route_requires_bearer(database_engine: sa.Engine, session_factory) -> None:
    tenant_id, _, membership_id, _ = _seed_principal(database_engine)
    _, assignment_id = _seed_case_and_assignment(
        session_factory,
        tenant_id=tenant_id,
        membership_id=membership_id,
        scope_actions=["assignment.acknowledge"],
    )
    client, _ = _client(session_factory)

    response = client.post(
        f"/api/v1/assignments/{assignment_id}/acknowledgement",
        json=_ack_payload(),
    )

    assert response.status_code == 401

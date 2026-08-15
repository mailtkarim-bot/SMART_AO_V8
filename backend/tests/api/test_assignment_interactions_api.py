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
            sa.text(
                "INSERT INTO tenants (id, slug, lifecycle) VALUES (:id, :slug, 'ACTIVE') "
                "ON CONFLICT (id) DO NOTHING"
            ),
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


def _seed_patron_case_and_target(
    session_factory: sessionmaker[Session],
    *,
    tenant_id: UUID,
) -> tuple[UUID, UUID]:
    target_identity_id = uuid4()
    target_membership_id = uuid4()
    case_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            IdentityRecord(
                id=target_identity_id,
                email_normalized=f"target-{target_identity_id.hex[:12]}@example.test",
                lifecycle="ACTIVE",
                email_verified_at=NOW,
            )
        )
        session.add(
            TenantMembershipRecord(
                id=target_membership_id,
                tenant_id=tenant_id,
                identity_id=target_identity_id,
                role="COLLABORATEUR",
                state="ACTIVE",
                activated_at=NOW,
                revoked_at=None,
            )
        )
        session.flush()
        session.add(
            CaseRecord(
                id=case_id,
                tenant_id=tenant_id,
                aggregate_revision=5,
                functional_identity_hash="c" * 64,
                title="Affaire HTTP patron",
                object_description=None,
                business_origin="MANUAL",
                origin_reference_id=None,
                origin_rationale="Test de façade patron",
                consultation_id=None,
                scope_kind="CUSTOM",
                scope_json={},
                scope_fingerprint="d" * 64,
                applicable_dce_version_id=None,
                lifecycle="ACTIVE",
                commercial_stage="ANALYSIS",
                decision_readiness="NOT_ASSESSED",
                dce_freshness="NO_DCE",
                responsibility_status="UNASSIGNED",
                stopped_reason=None,
                stopped_at=None,
                archived_reason=None,
                archived_at=None,
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
    return case_id, target_membership_id


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


def _patron_create_payload(target_membership_id: UUID) -> dict[str, str | int | list[str]]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "assignment_id": str(uuid4()),
        "target_membership_id": str(target_membership_id),
        "expected_case_revision": 5,
        "scope_actions": ["case.dce.read", "assignment.history.read"],
        "scope_classifications": ["INTERNAL_OPERATIONAL"],
        "starts_at": "2026-08-14T12:00:00Z",
        "ends_at": "2026-08-21T12:00:00Z",
    }


def _patron_end_payload(
    *,
    expected_revision: int = 0,
    end_reason_code: str = "PATRON_ENDED",
) -> dict[str, str | int]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": expected_revision,
        "end_reason_code": end_reason_code,
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


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_assignment_history_returns_closed_empty_then_bounded_history(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, membership_id, session_id = _seed_principal(database_engine)
    _, assignment_id = _seed_case_and_assignment(
        session_factory,
        tenant_id=tenant_id,
        membership_id=membership_id,
        scope_actions=[
            "assignment.acknowledge",
            "assignment.clarify",
            "assignment.history.read",
            "assignment.unavailability",
        ],
    )
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)

    empty = client.get(f"/api/v1/assignments/{assignment_id}/history", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    acknowledgement = client.post(
        f"/api/v1/assignments/{assignment_id}/acknowledgement",
        json=_ack_payload(),
        headers=headers,
    )
    clarification = client.post(
        f"/api/v1/assignments/{assignment_id}/clarification-requests",
        json={
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
            "correlation_id": str(uuid4()),
            "expected_revision": 1,
            "clarification_kind": "SCOPE",
            "subject": "Périmètre",
            "question": "Quel lot est prioritaire ?",
            "priority": "NORMAL",
        },
        headers=headers,
    )
    unavailability = client.post(
        f"/api/v1/assignments/{assignment_id}/unavailability-reports",
        json={
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
            "correlation_id": str(uuid4()),
            "expected_revision": 1,
            "reason_kind": "CAPACITY_CONFLICT",
            "reason": "Détail privé interdit à la lecture.",
            "unavailable_from": "2026-08-15T12:00:00Z",
            "known_deadline_impact": False,
        },
        headers=headers,
    )
    history = client.get(
        f"/api/v1/assignments/{assignment_id}/history?limit=2",
        headers=headers,
    )

    assert acknowledgement.status_code == 201
    assert clarification.status_code == 201
    assert unavailability.status_code == 201
    assert history.status_code == 200
    body = history.json()
    assert len(body["items"]) == 2
    assert {item["kind"] for item in body["items"]} <= {
        "ACKNOWLEDGEMENT",
        "CLARIFICATION_REQUEST",
        "UNAVAILABILITY_REPORT",
    }
    prohibited = {
        "actor_id",
        "command_id",
        "correlation_id",
        "functional_key",
        "membership_id",
        "note",
        "question",
        "reason",
        "requested_scope",
        "tenant_id",
    }
    assert not prohibited.intersection(body)
    assert all(not prohibited.intersection(item) for item in body["items"])


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_assignment_history_scope_denial_is_403_and_audited(
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

    response = client.get(
        f"/api/v1/assignments/{assignment_id}/history",
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "FORBIDDEN"}
    with session_factory() as session:
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord).where(
                SecurityAuditEventRecord.event_type == "AUTHZ_DENIED",
                SecurityAuditEventRecord.action == "assignment.history.read",
            )
        )
    assert audit is not None


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_assignment_history_foreign_assignment_is_neutral_404_and_audited(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, membership_id, session_id = _seed_principal(database_engine)
    other_tenant, _, other_membership_id, _ = _seed_principal(database_engine)
    _, foreign_assignment_id = _seed_case_and_assignment(
        session_factory,
        tenant_id=other_tenant,
        membership_id=other_membership_id,
        scope_actions=["assignment.history.read"],
    )
    client, tokens = _client(session_factory)

    response = client.get(
        f"/api/v1/assignments/{foreign_assignment_id}/history",
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "NOT_FOUND_OR_FORBIDDEN"}
    with session_factory() as session:
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord).where(
                SecurityAuditEventRecord.event_type == "AUTHZ_DENIED",
                SecurityAuditEventRecord.action == "assignment.history.read",
                SecurityAuditEventRecord.reason_code == "NOT_FOUND_OR_FORBIDDEN",
            )
        )
    assert audit is not None


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_assignment_history_requires_bearer(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, _, membership_id, _ = _seed_principal(database_engine)
    _, assignment_id = _seed_case_and_assignment(
        session_factory,
        tenant_id=tenant_id,
        membership_id=membership_id,
        scope_actions=["assignment.history.read"],
    )
    client, _ = _client(session_factory)

    response = client.get(f"/api/v1/assignments/{assignment_id}/history")

    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_assignment_creation_and_scope_amendment_return_closed_receipts(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(
        database_engine,
        role="PATRON_ADMIN",
    )
    case_id, target_membership_id = _seed_patron_case_and_target(
        session_factory,
        tenant_id=tenant_id,
    )
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    creation_payload = _patron_create_payload(target_membership_id)

    creation = client.post(
        f"/api/v1/patron/cases/{case_id}/assignments",
        json=creation_payload,
        headers=headers,
    )
    replay = client.post(
        f"/api/v1/patron/cases/{case_id}/assignments",
        json=creation_payload,
        headers=headers,
    )
    assignment_id = UUID(creation_payload["assignment_id"])
    amendment = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/scope-amendments",
        json={
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
            "correlation_id": str(uuid4()),
            "expected_revision": 0,
            "scope_actions": ["case.dce.read", "preparation.transmit"],
            "scope_classifications": ["INTERNAL_OPERATIONAL"],
        },
        headers=headers,
    )

    assert creation.status_code == 201
    assert replay.status_code == 200
    assert creation.json()["result_code"] == "CASE_ASSIGNMENT_CREATED"
    assert replay.json()["replayed"] is True
    assert amendment.status_code == 201
    assert amendment.json()["result_code"] == "CASE_ASSIGNMENT_SCOPE_AMENDED"
    prohibited = {"tenant_id", "target_membership_id", "scope_actions", "scope_classifications"}
    assert not prohibited.intersection(creation.json())
    assert not prohibited.intersection(amendment.json())


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_assignment_management_rejects_collaborator_and_foreign_case_neutrally(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(database_engine)
    other_tenant, _, _, _ = _seed_principal(database_engine)
    foreign_case_id, foreign_target_membership_id = _seed_patron_case_and_target(
        session_factory,
        tenant_id=other_tenant,
    )
    client, tokens = _client(session_factory)
    response = client.post(
        f"/api/v1/patron/cases/{foreign_case_id}/assignments",
        json=_patron_create_payload(foreign_target_membership_id),
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "FORBIDDEN"}
    with session_factory() as session:
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord).where(
                SecurityAuditEventRecord.event_type == "AUTHZ_DENIED",
                SecurityAuditEventRecord.action == "assignment.manage",
                SecurityAuditEventRecord.reason_code == "ASSIGNMENT_PATRON_REQUIRED",
            )
        )
    assert audit is not None

    patron_tenant, patron_identity_id, _, patron_session_id = _seed_principal(
        database_engine,
        role="PATRON_ADMIN",
    )
    del patron_tenant
    neutral = client.post(
        f"/api/v1/patron/cases/{foreign_case_id}/assignments",
        json=_patron_create_payload(foreign_target_membership_id),
        headers=_headers(
            tokens,
            identity_id=patron_identity_id,
            session_id=patron_session_id,
        ),
    )

    assert neutral.status_code == 404
    assert neutral.json() == {"detail": "NOT_FOUND_OR_FORBIDDEN"}


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_assignment_scope_payload_is_closed(
    database_engine: sa.Engine,
    session_factory,
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(
        database_engine,
        role="PATRON_ADMIN",
    )
    case_id, target_membership_id = _seed_patron_case_and_target(
        session_factory,
        tenant_id=tenant_id,
    )
    payload = _patron_create_payload(target_membership_id)
    payload["scope_actions"] = ["pricing.read"]
    client, tokens = _client(session_factory)

    response = client.post(
        f"/api/v1/patron/cases/{case_id}/assignments",
        json=payload,
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_assignment_suspension_returns_closed_receipt_and_replays(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(
        database_engine,
        role="PATRON_ADMIN",
    )
    case_id, target_membership_id = _seed_patron_case_and_target(
        session_factory,
        tenant_id=tenant_id,
    )
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    creation_payload = _patron_create_payload(target_membership_id)
    creation = client.post(
        f"/api/v1/patron/cases/{case_id}/assignments",
        json=creation_payload,
        headers=headers,
    )
    assignment_id = UUID(creation_payload["assignment_id"])
    suspension_payload = {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": 0,
        "suspension_reason_code": "CASE_PAUSED",
    }

    suspension = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/suspensions",
        json=suspension_payload,
        headers=headers,
    )
    replay = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/suspensions",
        json=suspension_payload,
        headers=headers,
    )

    assert creation.status_code == 201
    assert suspension.status_code == 201
    assert replay.status_code == 200
    assert suspension.json()["result_code"] == "CASE_ASSIGNMENT_SUSPENDED"
    assert replay.json()["replayed"] is True
    prohibited = {"tenant_id", "target_membership_id", "suspension_reason_code"}
    assert not prohibited.intersection(suspension.json())


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_assignment_suspension_requires_closed_reason(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(
        database_engine,
        role="PATRON_ADMIN",
    )
    case_id, target_membership_id = _seed_patron_case_and_target(
        session_factory,
        tenant_id=tenant_id,
    )
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    creation_payload = _patron_create_payload(target_membership_id)
    client.post(
        f"/api/v1/patron/cases/{case_id}/assignments",
        json=creation_payload,
        headers=headers,
    )

    response = client.post(
        f"/api/v1/patron/assignments/{creation_payload['assignment_id']}/suspensions",
        json={
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
            "expected_revision": 0,
            "suspension_reason_code": "FINANCIAL_APPROVAL",
        },
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_assignment_reactivation_returns_closed_receipt_and_replays(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(
        database_engine,
        role="PATRON_ADMIN",
    )
    case_id, target_membership_id = _seed_patron_case_and_target(
        session_factory,
        tenant_id=tenant_id,
    )
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    creation_payload = _patron_create_payload(target_membership_id)
    client.post(
        f"/api/v1/patron/cases/{case_id}/assignments",
        json=creation_payload,
        headers=headers,
    )
    assignment_id = UUID(creation_payload["assignment_id"])
    suspension = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/suspensions",
        json={
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
            "expected_revision": 0,
            "suspension_reason_code": "CASE_PAUSED",
        },
        headers=headers,
    )
    reactivation_payload = {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": 1,
        "reactivation_reason_code": "CASE_RESUMED",
    }

    reactivation = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/reactivations",
        json=reactivation_payload,
        headers=headers,
    )
    replay = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/reactivations",
        json=reactivation_payload,
        headers=headers,
    )

    assert suspension.status_code == 201
    assert reactivation.status_code == 201
    assert replay.status_code == 200
    assert reactivation.json()["result_code"] == "CASE_ASSIGNMENT_REACTIVATED"
    assert replay.json()["replayed"] is True
    prohibited = {"tenant_id", "target_membership_id", "reactivation_reason_code"}
    assert not prohibited.intersection(reactivation.json())


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_assignment_reactivation_requires_closed_reason(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(
        database_engine,
        role="PATRON_ADMIN",
    )
    case_id, target_membership_id = _seed_patron_case_and_target(
        session_factory,
        tenant_id=tenant_id,
    )
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    creation_payload = _patron_create_payload(target_membership_id)
    client.post(
        f"/api/v1/patron/cases/{case_id}/assignments",
        json=creation_payload,
        headers=headers,
    )
    assignment_id = UUID(creation_payload["assignment_id"])
    client.post(
        f"/api/v1/patron/assignments/{assignment_id}/suspensions",
        json={
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
            "expected_revision": 0,
            "suspension_reason_code": "CASE_PAUSED",
        },
        headers=headers,
    )

    response = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/reactivations",
        json={
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
            "expected_revision": 1,
            "reactivation_reason_code": "PRICING_REVIEWED",
        },
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_assignment_end_returns_closed_receipt_and_replays(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(database_engine, role="PATRON_ADMIN")
    case_id, target_membership_id = _seed_patron_case_and_target(
        session_factory,
        tenant_id=tenant_id,
    )
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    creation_payload = _patron_create_payload(target_membership_id)
    creation = client.post(
        f"/api/v1/patron/cases/{case_id}/assignments",
        json=creation_payload,
        headers=headers,
    )
    assignment_id = UUID(creation_payload["assignment_id"])
    end_payload = _patron_end_payload(end_reason_code="CASE_ARCHIVED")

    ending = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/end",
        json=end_payload,
        headers=headers,
    )
    replay = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/end",
        json=end_payload,
        headers=headers,
    )

    assert creation.status_code == 201
    assert ending.status_code == 201
    assert replay.status_code == 200
    assert ending.json()["result_code"] == "CASE_ASSIGNMENT_ENDED"
    assert replay.json()["replayed"] is True
    prohibited = {"tenant_id", "target_membership_id", "end_reason_code", "ended_at"}
    assert not prohibited.intersection(ending.json())


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_assignment_end_rejects_non_patron_and_foreign_resource_neutrally(
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
    payload = _patron_end_payload()

    forbidden = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/end",
        json=payload,
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert forbidden.status_code == 403
    assert forbidden.json() == {"detail": "FORBIDDEN"}

    patron_tenant, patron_identity_id, _, patron_session_id = _seed_principal(
        database_engine,
        role="PATRON_ADMIN",
    )
    del patron_tenant
    neutral = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/end",
        json=_patron_end_payload(),
        headers=_headers(
            tokens,
            identity_id=patron_identity_id,
            session_id=patron_session_id,
        ),
    )

    assert neutral.status_code == 404
    assert neutral.json() == {"detail": "NOT_FOUND_OR_FORBIDDEN"}


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_assignment_end_maps_stale_revision_to_conflict(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(database_engine, role="PATRON_ADMIN")
    case_id, target_membership_id = _seed_patron_case_and_target(
        session_factory,
        tenant_id=tenant_id,
    )
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    creation_payload = _patron_create_payload(target_membership_id)
    client.post(
        f"/api/v1/patron/cases/{case_id}/assignments",
        json=creation_payload,
        headers=headers,
    )

    response = client.post(
        f"/api/v1/patron/assignments/{creation_payload['assignment_id']}/end",
        json=_patron_end_payload(expected_revision=1),
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "VERSION_CONFLICT"}


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_assignment_end_requires_closed_reason(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(database_engine, role="PATRON_ADMIN")
    case_id, target_membership_id = _seed_patron_case_and_target(
        session_factory,
        tenant_id=tenant_id,
    )
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    creation_payload = _patron_create_payload(target_membership_id)
    client.post(
        f"/api/v1/patron/cases/{case_id}/assignments",
        json=creation_payload,
        headers=headers,
    )

    response = client.post(
        f"/api/v1/patron/assignments/{creation_payload['assignment_id']}/end",
        json=_patron_end_payload(end_reason_code="PRICING_APPROVED"),
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_assignment_cockpit_lists_filtered_assignments_and_closed_journal(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(database_engine, role="PATRON_ADMIN")
    case_id, target_membership_id = _seed_patron_case_and_target(
        session_factory,
        tenant_id=tenant_id,
    )
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    creation_payload = _patron_create_payload(target_membership_id)
    creation = client.post(
        f"/api/v1/patron/cases/{case_id}/assignments",
        json=creation_payload,
        headers=headers,
    )
    assignment_id = UUID(creation_payload["assignment_id"])

    active_list = client.get(
        "/api/v1/patron/assignments",
        params={"case_id": str(case_id), "state": "ACTIVE", "limit": 1},
        headers=headers,
    )
    ending = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/end",
        json=_patron_end_payload(end_reason_code="CASE_STOPPED"),
        headers=headers,
    )
    ended_list = client.get(
        "/api/v1/patron/assignments",
        params={"case_id": str(case_id), "state": "ENDED", "limit": 1},
        headers=headers,
    )
    journal = client.get(
        f"/api/v1/patron/assignments/{assignment_id}/journal",
        params={"limit": 2},
        headers=headers,
    )

    assert creation.status_code == 201
    assert active_list.status_code == 200
    assert active_list.json()["items"][0]["assignment_id"] == str(assignment_id)
    assert active_list.json()["items"][0]["state"] == "ACTIVE"
    assert ending.status_code == 201
    assert ended_list.status_code == 200
    assert ended_list.json()["items"][0]["state"] == "ENDED"
    assert ended_list.json()["items"][0]["ended_at"] is not None
    assert journal.status_code == 200
    assert journal.json()["assignment"]["state"] == "ENDED"
    assert {item["event_type"] for item in journal.json()["items"]} == {
        "ASSIGNMENT_CREATED",
        "ASSIGNMENT_ENDED",
    }
    prohibited_assignment = {
        "tenant_id",
        "membership_id",
        "granted_by_membership_id",
        "command_id",
        "correlation_id",
    }
    prohibited_journal = prohibited_assignment | {"author_membership_id", "target_membership_id"}
    assert not prohibited_assignment.intersection(ended_list.json()["items"][0])
    assert not prohibited_journal.intersection(journal.json()["items"][0])


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_assignment_cockpit_denies_collaborator_and_hides_foreign_journal(
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

    forbidden = client.get(
        "/api/v1/patron/assignments",
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert forbidden.status_code == 403
    assert forbidden.json() == {"detail": "FORBIDDEN"}
    with session_factory() as session:
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord).where(
                SecurityAuditEventRecord.event_type == "AUTHZ_DENIED",
                SecurityAuditEventRecord.action == "assignment.manage",
                SecurityAuditEventRecord.reason_code == "ASSIGNMENT_PATRON_REQUIRED",
            )
        )
    assert audit is not None

    patron_tenant, patron_identity_id, _, patron_session_id = _seed_principal(
        database_engine,
        role="PATRON_ADMIN",
    )
    del patron_tenant
    neutral = client.get(
        f"/api/v1/patron/assignments/{assignment_id}/journal",
        headers=_headers(
            tokens,
            identity_id=patron_identity_id,
            session_id=patron_session_id,
        ),
    )

    assert neutral.status_code == 404
    assert neutral.json() == {"detail": "NOT_FOUND_OR_FORBIDDEN"}


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_assignment_cockpit_requires_bearer_and_valid_bounded_parameters(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, session_id = _seed_principal(database_engine, role="PATRON_ADMIN")
    del tenant_id
    client, tokens = _client(session_factory)

    missing_bearer = client.get("/api/v1/patron/assignments")
    invalid_limit = client.get(
        "/api/v1/patron/assignments",
        params={"limit": 0},
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )
    invalid_state = client.get(
        "/api/v1/patron/assignments",
        params={"state": "PENDING_REVIEW"},
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert missing_bearer.status_code == 401
    assert invalid_limit.status_code == 422
    assert invalid_state.status_code == 422


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_reads_closed_collaborator_interactions_with_kind_filter(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, patron_identity_id, _, patron_session_id = _seed_principal(
        database_engine,
        role="PATRON_ADMIN",
    )
    (
        _,
        collaborator_identity_id,
        collaborator_membership_id,
        collaborator_session_id,
    ) = _seed_principal(
        database_engine,
        tenant_id=tenant_id,
    )
    _, assignment_id = _seed_case_and_assignment(
        session_factory,
        tenant_id=tenant_id,
        membership_id=collaborator_membership_id,
        scope_actions=[
            "assignment.acknowledge",
            "assignment.clarify",
            "assignment.unavailability",
        ],
    )
    client, tokens = _client(session_factory)
    collaborator_headers = _headers(
        tokens,
        identity_id=collaborator_identity_id,
        session_id=collaborator_session_id,
    )
    patron_headers = _headers(
        tokens,
        identity_id=patron_identity_id,
        session_id=patron_session_id,
    )

    acknowledgement = client.post(
        f"/api/v1/assignments/{assignment_id}/acknowledgement",
        json=_ack_payload(),
        headers=collaborator_headers,
    )
    clarification = client.post(
        f"/api/v1/assignments/{assignment_id}/clarification-requests",
        json={
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
            "correlation_id": str(uuid4()),
            "expected_revision": 1,
            "clarification_kind": "DEADLINE",
            "subject": "Date de remise",
            "question": "La visite reste-t-elle obligatoire ?",
            "requested_scope": "Lot clos-couvert",
            "priority": "HIGH",
        },
        headers=collaborator_headers,
    )
    unavailability = client.post(
        f"/api/v1/assignments/{assignment_id}/unavailability-reports",
        json={
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
            "correlation_id": str(uuid4()),
            "expected_revision": 1,
            "reason_kind": "CAPACITY_CONFLICT",
            "reason": "Conflit de capacité signalé.",
            "unavailable_from": "2026-08-15T12:00:00Z",
            "unavailable_until": "2026-08-17T12:00:00Z",
            "known_deadline_impact": True,
            "impact_note": "Une vérification patron est utile.",
        },
        headers=collaborator_headers,
    )
    interactions = client.get(
        f"/api/v1/patron/assignments/{assignment_id}/interactions",
        params={"limit": 3},
        headers=patron_headers,
    )
    clarifications = client.get(
        f"/api/v1/patron/assignments/{assignment_id}/interactions",
        params={"kind": "CLARIFICATION_REQUEST", "limit": 1},
        headers=patron_headers,
    )

    assert acknowledgement.status_code == 201
    assert clarification.status_code == 201
    assert unavailability.status_code == 201
    assert interactions.status_code == 200
    assert interactions.json()["assignment_id"] == str(assignment_id)
    assert {item["kind"] for item in interactions.json()["items"]} == {
        "ACKNOWLEDGEMENT",
        "CLARIFICATION_REQUEST",
        "UNAVAILABILITY_REPORT",
    }
    assert clarifications.status_code == 200
    assert clarifications.json()["items"][0]["kind"] == "CLARIFICATION_REQUEST"
    assert clarifications.json()["items"][0]["clarification_kind"] == "DEADLINE"
    prohibited = {
        "tenant_id",
        "actor_id",
        "membership_id",
        "note",
        "subject",
        "question",
        "requested_scope",
        "reason",
        "impact_note",
        "command_id",
        "correlation_id",
        "functional_key",
    }
    assert not prohibited.intersection(interactions.json())
    for item in interactions.json()["items"]:
        assert not prohibited.intersection(item)


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_interactions_read_denies_collaborator_and_hides_foreign_assignment(
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
    collaborator_headers = _headers(tokens, identity_id=identity_id, session_id=session_id)

    forbidden = client.get(
        f"/api/v1/patron/assignments/{assignment_id}/interactions",
        headers=collaborator_headers,
    )

    assert forbidden.status_code == 403
    assert forbidden.json() == {"detail": "FORBIDDEN"}
    with session_factory() as session:
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord).where(
                SecurityAuditEventRecord.event_type == "AUTHZ_DENIED",
                SecurityAuditEventRecord.action == "assignment.manage",
                SecurityAuditEventRecord.resource_type == "CASE_ASSIGNMENT_INTERACTIONS",
                SecurityAuditEventRecord.reason_code == "ASSIGNMENT_PATRON_REQUIRED",
            )
        )
    assert audit is not None

    _, patron_identity_id, _, patron_session_id = _seed_principal(
        database_engine,
        role="PATRON_ADMIN",
    )
    neutral = client.get(
        f"/api/v1/patron/assignments/{assignment_id}/interactions",
        headers=_headers(
            tokens,
            identity_id=patron_identity_id,
            session_id=patron_session_id,
        ),
    )

    assert neutral.status_code == 404
    assert neutral.json() == {"detail": "NOT_FOUND_OR_FORBIDDEN"}


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_interactions_read_requires_bearer_and_valid_parameters(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, membership_id, session_id = _seed_principal(
        database_engine,
        role="PATRON_ADMIN",
    )
    _, assignment_id = _seed_case_and_assignment(
        session_factory,
        tenant_id=tenant_id,
        membership_id=membership_id,
        scope_actions=["assignment.acknowledge"],
    )
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    route = f"/api/v1/patron/assignments/{assignment_id}/interactions"

    missing_bearer = client.get(route)
    invalid_limit = client.get(route, params={"limit": 0}, headers=headers)
    invalid_kind = client.get(route, params={"kind": "FREE_TEXT"}, headers=headers)

    assert missing_bearer.status_code == 401
    assert invalid_limit.status_code == 422
    assert invalid_kind.status_code == 422


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_validates_acknowledgement_with_closed_receipt_and_replay(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, patron_identity_id, _, patron_session_id = _seed_principal(
        database_engine,
        role="PATRON_ADMIN",
    )
    (
        _,
        collaborator_identity_id,
        collaborator_membership_id,
        collaborator_session_id,
    ) = _seed_principal(database_engine, tenant_id=tenant_id)
    _, assignment_id = _seed_case_and_assignment(
        session_factory,
        tenant_id=tenant_id,
        membership_id=collaborator_membership_id,
        scope_actions=["assignment.acknowledge"],
    )
    client, tokens = _client(session_factory)
    collaborator_headers = _headers(
        tokens,
        identity_id=collaborator_identity_id,
        session_id=collaborator_session_id,
    )
    patron_headers = _headers(
        tokens,
        identity_id=patron_identity_id,
        session_id=patron_session_id,
    )
    acknowledgement = client.post(
        f"/api/v1/assignments/{assignment_id}/acknowledgement",
        json=_ack_payload(),
        headers=collaborator_headers,
    )
    interactions = client.get(
        f"/api/v1/patron/assignments/{assignment_id}/interactions",
        params={"kind": "ACKNOWLEDGEMENT"},
        headers=patron_headers,
    )
    validation_payload = {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "interaction_id": interactions.json()["items"][0]["record_id"],
        "interaction_kind": "ACKNOWLEDGEMENT",
        "validation_code": "ACKNOWLEDGEMENT_NOTED",
    }

    validation = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/interaction-validations",
        json=validation_payload,
        headers=patron_headers,
    )
    replay = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/interaction-validations",
        json=validation_payload,
        headers=patron_headers,
    )
    duplicate = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/interaction-validations",
        json={
            **validation_payload,
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
        },
        headers=patron_headers,
    )

    assert acknowledgement.status_code == 201
    assert interactions.status_code == 200
    assert validation.status_code == 201
    assert replay.status_code == 200
    assert validation.json()["result_code"] == "INTERACTION_VALIDATED"
    assert replay.json()["replayed"] is True
    assert duplicate.status_code == 422
    prohibited = {"interaction_id", "interaction_kind", "validation_code", "tenant_id"}
    assert not prohibited.intersection(validation.json())


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_interaction_validation_denies_collaborator_and_hides_foreign_assignment(
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
    payload = {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "interaction_id": str(uuid4()),
        "interaction_kind": "ACKNOWLEDGEMENT",
        "validation_code": "ACKNOWLEDGEMENT_NOTED",
    }

    forbidden = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/interaction-validations",
        json=payload,
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )
    _, patron_identity_id, _, patron_session_id = _seed_principal(
        database_engine,
        role="PATRON_ADMIN",
    )
    neutral = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/interaction-validations",
        json=payload,
        headers=_headers(
            tokens,
            identity_id=patron_identity_id,
            session_id=patron_session_id,
        ),
    )
    invalid_pair = client.post(
        f"/api/v1/patron/assignments/{assignment_id}/interaction-validations",
        json={**payload, "validation_code": "CLARIFICATION_NOTED"},
        headers=_headers(
            tokens,
            identity_id=patron_identity_id,
            session_id=patron_session_id,
        ),
    )

    assert forbidden.status_code == 403
    assert forbidden.json() == {"detail": "FORBIDDEN"}
    assert neutral.status_code == 404
    assert neutral.json() == {"detail": "NOT_FOUND_OR_FORBIDDEN"}
    assert invalid_pair.status_code == 422

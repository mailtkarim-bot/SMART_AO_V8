import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from app.bootstrap.application import AppRuntime, create_app
from app.interfaces.http.routes.authentication import AuthenticationHttpRuntime
from app.platform.security.authentication import AuthenticationService
from app.platform.security.models import AuthSessionRecord
from app.platform.security.tokens import JwtAccessTokenCodec
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application"))
from test_collab_work_task import _seed  # noqa: E402

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class UnusedPasswordVerifier:
    def verify(self, *, password_hash: str, password: str) -> bool:
        return False


class UnusedTokenGenerator:
    def generate(self) -> str:
        return "unused-refresh-token"






def _client(session_factory):
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
    return TestClient(
        create_app(
            runtime=AppRuntime.create(session_factory=session_factory),
            authentication_runtime=auth_runtime,
        ),
        base_url="https://smart-ao.test",
    ), tokens


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_collaborator_task_create_replay_and_read_model(session_factory) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    with session_factory.begin() as session:
        session.add(
            AuthSessionRecord(
                id=actor.session_id,
                tenant_id=actor.tenant_id,
                membership_id=actor.membership_id,
                identity_id=actor.identity_id,
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
    client, tokens = _client(session_factory)
    token = tokens.issue(
        identity_id=actor.identity_id,
        session_id=actor.session_id,
        token_version=1,
    )
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "requirement_id": str(requirement_id),
        "task_kind": "REQUIREMENT_CHECK",
        "title": "Vérifier la pièce de candidature",
        "objective": "Confirmer la source et signaler tout manque.",
    }
    first = client.post(
        f"/api/v1/collaborator/cases/{case_id}/assignments/{assignment_id}/tasks",
        json=payload,
        headers=headers,
    )
    replay = client.post(
        f"/api/v1/collaborator/cases/{case_id}/assignments/{assignment_id}/tasks",
        json=payload,
        headers=headers,
    )
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert "price" not in str(first.json()).lower()
    task_id = first.json()["aggregate_refs"][0]["aggregate_id"]

    listing = client.get(f"/api/v1/collaborator/cases/{case_id}/tasks", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["tasks"][0]["task_id"] == task_id
    assert "financial" not in str(listing.json()).lower()


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_collaborator_information_request_and_blocker_http_workflow(session_factory) -> None:
    from datetime import timedelta

    from app.platform.security.models import AuthSessionRecord

    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    with session_factory.begin() as session:
        session.add(
            AuthSessionRecord(
                id=actor.session_id,
                tenant_id=actor.tenant_id,
                membership_id=actor.membership_id,
                identity_id=actor.identity_id,
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
    client, tokens = _client(session_factory)
    token = tokens.issue(
        identity_id=actor.identity_id,
        session_id=actor.session_id,
        token_version=1,
    )
    headers = {"Authorization": f"Bearer {token}"}
    create_payload = {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "requirement_id": str(requirement_id),
        "task_kind": "REQUIREMENT_CHECK",
        "title": "Vérifier la source",
        "objective": "Contrôler la page de référence.",
    }
    task_response = client.post(
        f"/api/v1/collaborator/cases/{case_id}/assignments/{assignment_id}/tasks",
        json=create_payload,
        headers=headers,
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["aggregate_refs"][0]["aggregate_id"]

    request_payload = {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_task_revision": 0,
        "request_kind": "MISSING_SOURCE",
        "subject": "Source de l’exigence",
        "question": "Pouvez-vous confirmer la page du RC ?",
        "requested_object": "Localisation de la source",
        "reason": "La source est nécessaire pour le contrôle.",
        "priority": "HIGH",
    }
    request_response = client.post(
        f"/api/v1/collaborator/tasks/{task_id}/information-requests",
        json=request_payload,
        headers=headers,
    )
    request_replay = client.post(
        f"/api/v1/collaborator/tasks/{task_id}/information-requests",
        json=request_payload,
        headers=headers,
    )
    assert request_response.status_code == 201
    assert request_replay.status_code == 200
    assert request_replay.json()["replayed"] is True
    request_id = request_response.json()["aggregate_refs"][0]["aggregate_id"]

    workflow = client.get(f"/api/v1/collaborator/tasks/{task_id}/workflow", headers=headers)
    assert workflow.status_code == 200
    assert workflow.json()["information_requests"][0]["request_id"] == request_id
    assert workflow.json()["blockers"] == []

    blocker_command_id = str(uuid4())
    blocker_payload = {
        "command_id": blocker_command_id,
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": 0,
        "blocker_kind": "MISSING_INFORMATION",
        "description": "La source doit être confirmée.",
        "source_locator": "RC:p8",
        "resolution_owner": "COLLABORATEUR",
    }
    blocked = client.post(
        f"/api/v1/collaborator/tasks/{task_id}/blockers",
        json=blocker_payload,
        headers=headers,
    )
    assert blocked.status_code == 201
    blocker_id = blocker_command_id
    blocked_workflow = client.get(f"/api/v1/collaborator/tasks/{task_id}/workflow", headers=headers)
    assert blocked_workflow.status_code == 200
    assert blocked_workflow.json()["state"] == "BLOCKED"

    resolved = client.post(
        f"/api/v1/collaborator/tasks/{task_id}/blockers/{blocker_id}/resolve",
        json={
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
            "correlation_id": str(uuid4()),
            "expected_revision": 1,
            "resolution_note": "La source RC:p8 est confirmée.",
        },
        headers=headers,
    )
    assert resolved.status_code == 201
    final_workflow = client.get(f"/api/v1/collaborator/tasks/{task_id}/workflow", headers=headers)
    assert final_workflow.status_code == 200
    assert final_workflow.json()["state"] == "IN_PROGRESS"
    assert "price" not in str(final_workflow.json()).lower()
    assert "margin" not in str(final_workflow.json()).lower()

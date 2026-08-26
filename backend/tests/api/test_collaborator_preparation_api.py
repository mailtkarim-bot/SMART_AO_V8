from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.bootstrap.application import AppRuntime, create_app
from app.interfaces.http.routes.authentication import AuthenticationHttpRuntime
from app.modules.dce.infrastructure.models.dce_requirement_confirmations import (
    DceRequirementConfirmationCurrentRecord,
    DceRequirementConfirmationRecord,
)
from app.platform.security.authentication import AuthenticationService
from app.platform.security.capabilities import Capability
from app.platform.security.models import AuthSessionRecord, CaseAssignmentRecord
from app.platform.security.tokens import JwtAccessTokenCodec
from fastapi.testclient import TestClient

from tests.application.test_collab_work_task import NOW, _seed

pytest_plugins = ("tests.application.test_collab_work_task",)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class UnusedPasswordVerifier:
    def verify(self, *, password_hash: str, password: str) -> bool:
        return False


class UnusedTokenGenerator:
    def generate(self) -> str:
        return "unused-refresh-token"


def _client(session_factory, *, storage_root: Path) -> tuple[TestClient, JwtAccessTokenCodec]:
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


def _enable_preparation_scope(session_factory, assignment_id: object) -> None:
    with session_factory.begin() as session:
        assignment = session.get(CaseAssignmentRecord, assignment_id)
        assignment.scope_actions_json = [
            Capability.WORK_TASK_READ.value,
            Capability.WORK_TASK_WRITE.value,
            Capability.PREPARATION_READINESS_WRITE.value,
            Capability.PREPARATION_DOCUMENT_WRITE.value,
        ]


def _confirm_requirement(session_factory, *, actor, requirement_id) -> None:
    confirmation_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            DceRequirementConfirmationRecord(
                id=confirmation_id,
                tenant_id=actor.tenant_id,
                requirement_id=requirement_id,
                revision=1,
                previous_confirmation_id=None,
                outcome="CONFIRMED",
                reason_code="SOURCE_REVIEWED",
                confirmed_by_actor_id=actor.actor_id,
            )
        )
        session.flush()
        session.add(
            DceRequirementConfirmationCurrentRecord(
                tenant_id=actor.tenant_id,
                requirement_id=requirement_id,
                confirmation_id=confirmation_id,
                revision=1,
                outcome="CONFIRMED",
            )
        )


def test_collaborator_preparation_readiness_generation_and_public_projection(
    session_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SMART_AO_DCE_QUARANTINE_ROOT", str(tmp_path / "private-dce"))
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    _enable_preparation_scope(session_factory, assignment_id)
    dce_version_id = _dce_version_id(session_factory, actor.tenant_id)
    package_id = uuid4()
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
    client, tokens = _client(session_factory, storage_root=tmp_path / "private-dce")
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
        "package_id": str(package_id),
        "assignment_id": str(assignment_id),
        "dce_version_id": str(dce_version_id),
        "expected_revision": 0,
    }
    first = client.post(
        f"/api/v1/collaborator/cases/{case_id}/preparation/readiness",
        json=payload,
        headers=headers,
    )
    replay = client.post(
        f"/api/v1/collaborator/cases/{case_id}/preparation/readiness",
        json=payload,
        headers=headers,
    )
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert first.json()["result_code"] == "PREPARATION_READINESS_EVALUATED"

    blocked_projection = client.get(
        f"/api/v1/collaborator/preparation/{package_id}", headers=headers
    )
    assert blocked_projection.status_code == 200
    assert blocked_projection.json()["latest_readiness"]["state"] == "BLOCKED"
    assert not any(
        term in str(blocked_projection.json()).lower()
        for term in ("price", "prix", "cost", "coût", "margin", "marge", "financial", "finance")
    )

    _confirm_requirement(session_factory, actor=actor, requirement_id=requirement_id)
    ready_payload = {
        **payload,
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "expected_revision": 1,
    }
    ready = client.post(
        f"/api/v1/collaborator/cases/{case_id}/preparation/readiness",
        json=ready_payload,
        headers=headers,
    )
    assert ready.status_code == 201
    assert ready.json()["result_code"] == "PREPARATION_READINESS_EVALUATED"

    document = client.post(
        f"/api/v1/collaborator/preparation/{package_id}/documents",
        json={
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
            "correlation_id": str(uuid4()),
            "expected_revision": 2,
            "readiness_revision": 2,
            "document_kind": "TECHNICAL_RESPONSE",
        },
        headers=headers,
    )
    assert document.status_code == 201
    assert document.json()["result_code"] == "TECHNICAL_DOCUMENT_GENERATED"

    generated_controlled = []
    for expected_revision, document_kind in ((3, "DC1"), (4, "DC2"), (5, "DC4")):
        controlled = client.post(
            f"/api/v1/collaborator/preparation/{package_id}/documents",
            json={
                "command_id": str(uuid4()),
                "idempotency_key": str(uuid4()),
                "correlation_id": str(uuid4()),
                "expected_revision": expected_revision,
                "readiness_revision": 2,
                "document_kind": document_kind,
            },
            headers=headers,
        )
        assert controlled.status_code == 201
        assert controlled.json()["result_code"] == "CONTROLLED_DRAFT_GENERATED"
        generated_controlled.append(controlled)

    assert len(generated_controlled) == 3
    projection = client.get(f"/api/v1/collaborator/preparation/{package_id}", headers=headers)
    assert projection.status_code == 200
    body = projection.json()
    assert body["state"] == "GENERATED"
    assert body["latest_readiness"]["state"] == "READY"
    assert [item["document_kind"] for item in body["generated_documents"]] == [
        "TECHNICAL_RESPONSE",
        "DC1",
        "DC2",
        "DC4",
    ]
    assert [item["version"] for item in body["generated_documents"]] == [1, 2, 3, 4]
    assert set(body["generated_documents"][0]) == {
        "document_id",
        "version",
        "document_kind",
        "state",
        "readiness_revision",
    }
    assert "storage_key" not in str(body)
    assert "content_sha256" not in str(body)


def _dce_version_id(session_factory, tenant_id):
    from app.modules.dce.infrastructure.models.dce_version import DceVersionRecord

    with session_factory() as session:
        return session.scalar(
            sa.select(DceVersionRecord.id).where(DceVersionRecord.tenant_id == tenant_id)
        )

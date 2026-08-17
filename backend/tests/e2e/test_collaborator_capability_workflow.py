from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.platform.security.models import CaseCapabilityGapRecord, CaseCapabilityProposalRecord
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from test_collab_capability import _seed  # noqa: E402
from test_collaborator_capability_api import (  # noqa: E402
    _auth_session,
    _client,
    _headers,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = os.getenv("SMART_AO_TEST_DATABASE_URL") or (
    "postgresql+psycopg://" + "smart_ao" + ":" + "smart_ao" + "@127.0.0.1:5432/smart_ao"
)


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
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))
    return sessionmaker(bind=database_engine, expire_on_commit=False)


@pytest.mark.e2e
@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_end_to_end_collaborator_proposal_gap_and_read_workflow(
    session_factory: sessionmaker[Session],
) -> None:
    actor, assignment_id, case_id, requirement_id, capability_id, version_id = _seed(
        session_factory
    )
    _auth_session(session_factory, actor)
    client, tokens = _client(session_factory)
    headers = _headers(tokens, actor)
    proposal_payload = {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "assignment_id": str(assignment_id),
        "capability_id": str(capability_id),
        "capability_version_id": str(version_id),
        "requirement_id": str(requirement_id),
        "justification": "La qualification répond à l’exigence Case.",
        "source_locator": "RC p. 12",
    }
    proposal = client.post(
        f"/api/v1/collaborator/cases/{case_id}/capability-proposals",
        json=proposal_payload,
        headers=headers,
    )
    replay = client.post(
        f"/api/v1/collaborator/cases/{case_id}/capability-proposals",
        json=proposal_payload,
        headers=headers,
    )
    gap = client.post(
        f"/api/v1/collaborator/cases/{case_id}/capability-gaps",
        json={
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
            "correlation_id": str(uuid4()),
            "assignment_id": str(assignment_id),
            "capability_id": str(capability_id),
            "requirement_id": str(requirement_id),
            "gap_kind": "EXPIRED",
            "severity": "IMPORTANT",
            "reason": "La preuve doit être renouvelée avant transmission.",
            "source_locator": "RC p. 13",
            "recommended_action": "Demander une preuve actuelle au patron.",
        },
        headers=headers,
    )
    read = client.get(
        f"/api/v1/collaborator/cases/{case_id}/capability-assessments",
        params={"assignment_id": str(assignment_id)},
        headers=headers,
    )

    assert proposal.status_code == 201, proposal.text
    assert replay.status_code == 200, replay.text
    assert replay.json()["replayed"] is True
    assert gap.status_code == 201, gap.text
    assert read.status_code == 200, read.text
    assert len(read.json()["proposals"]) == 1
    assert read.json()["proposals"][0]["validity_state"] == "CURRENT"
    assert read.json()["gaps"][0]["gap_kind"] == "EXPIRED"
    assert "tenant_id" not in str(read.json())
    assert "price" not in str(read.json()).lower()
    assert "margin" not in str(read.json()).lower()
    with session_factory() as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(CaseCapabilityProposalRecord))
            == 1
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(CaseCapabilityGapRecord)) == 1

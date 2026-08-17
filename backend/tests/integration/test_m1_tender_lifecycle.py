from __future__ import annotations

from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.demonstrations.m1 import M1ScenarioRunner
from sqlalchemy.orm import Session, sessionmaker


def _insert_tenant(engine: sa.Engine) -> str:
    tenant_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO tenants (id, slug, lifecycle) VALUES (:id, :slug, 'ACTIVE')"
            ),
            {"id": tenant_id, "slug": f"m1-tenant-{tenant_id}"},
        )
    return tenant_id


@pytest.mark.integration
@pytest.mark.db
def test_m1_scenario_preserves_decision_and_case_history_after_rectification(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    result = M1ScenarioRunner(session_factory=session_factory).run(
        tenant_id=tenant_id,
        actor_id=str(uuid4()),
    )

    with Session(database_engine) as session:
        dce_versions = session.execute(
            sa.text(
                """
                SELECT id, lifecycle, corpus_hash, predecessor_dce_version_id
                FROM dce_versions
                WHERE tenant_id = :tenant_id
                ORDER BY source_received_at, id
                """
            ),
            {"tenant_id": tenant_id},
        ).mappings().all()
        case = session.execute(
            sa.text(
                """
                SELECT commercial_stage, dce_freshness, applicable_dce_version_id
                FROM cases
                WHERE tenant_id = :tenant_id AND id = :case_id
                """
            ),
            {"tenant_id": tenant_id, "case_id": str(result.case_id)},
        ).mappings().one()
        decision = session.execute(
            sa.text(
                """
                SELECT lifecycle, outcome, validity, context_status, selected_final_context_id
                FROM decisions
                WHERE tenant_id = :tenant_id AND id = :decision_id
                """
            ),
            {"tenant_id": tenant_id, "decision_id": str(result.decision_id)},
        ).mappings().one()
        current_history_count = session.execute(
            sa.text(
                """
                SELECT count(*)
                FROM case_dce_applicability_history
                WHERE tenant_id = :tenant_id AND case_id = :case_id
                """
            ),
            {"tenant_id": tenant_id, "case_id": str(result.case_id)},
        ).scalar_one()

    assert result.consultation_id
    assert len(dce_versions) == 2
    assert dce_versions[0]["id"] == result.initial_dce_version_id
    assert dce_versions[0]["lifecycle"] == "SUPERSEDED"
    assert dce_versions[1]["id"] == result.rectification_dce_version_id
    assert dce_versions[1]["lifecycle"] == "ADMITTED"
    assert dce_versions[1]["predecessor_dce_version_id"] == result.initial_dce_version_id
    assert dce_versions[0]["corpus_hash"] != dce_versions[1]["corpus_hash"]
    assert case["commercial_stage"] == "AWAITING_DECISION"
    assert case["dce_freshness"] == "REVIEW_REQUIRED"
    assert case["applicable_dce_version_id"] == result.initial_dce_version_id
    assert current_history_count == 1
    assert decision == {
        "lifecycle": "FINALIZED",
        "outcome": "GO",
        "validity": "REVIEW_REQUIRED",
        "context_status": "STALE",
        "selected_final_context_id": result.decision_context_id,
    }

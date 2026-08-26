from __future__ import annotations

import pytest
import sqlalchemy as sa


@pytest.mark.db
def test_risk_treatment_transition_table_and_trigger_exist(database_engine: sa.Engine) -> None:
    inspector = sa.inspect(database_engine)

    tables = set(inspector.get_table_names())
    assert "decision_risks" in tables
    assert "decision_risk_treatment_transitions" in tables

    columns = {
        column["name"]
        for column in inspector.get_columns("decision_risk_treatment_transitions")
    }
    assert {
        "risk_id",
        "from_treatment",
        "to_treatment",
        "evidence_excerpt",
        "evidence_locator_json",
        "aggregate_revision",
        "rationale",
    }.issubset(columns)

    with database_engine.connect() as connection:
        trigger_exists = connection.scalar(
            sa.text(
                "SELECT EXISTS ("
                "SELECT 1 FROM pg_trigger "
                "WHERE tgname = 'trg_decision_risk_treatment_transitions_append_only'"
                ")"
            )
        )
    assert trigger_exists is True


@pytest.mark.db
def test_risk_treatment_transition_constraints_are_forward_only(
    database_engine: sa.Engine,
) -> None:
    constraints = sa.inspect(database_engine).get_check_constraints(
        "decision_risk_treatment_transitions"
    )
    definitions = " ".join(str(constraint.get("sqltext", "")) for constraint in constraints)

    assert "from_treatment = 'OPEN'" in definitions
    assert "to_treatment IN ('ACCEPTED', 'MITIGATED')" in definitions
    assert "from_treatment = 'ACCEPTED'" in definitions
    assert "to_treatment = 'MITIGATED'" in definitions
    assert "aggregate_revision > 1" in definitions

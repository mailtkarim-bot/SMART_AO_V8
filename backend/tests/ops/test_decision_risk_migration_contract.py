from pathlib import Path

MIGRATION = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "20260824_0058_create_decision_risks.py"
)
TRANSITION_MIGRATION = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "20260826_0065_decision_risk_treatment_transitions.py"
)


def test_decision_risk_migration_declares_append_only_trigger() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE FUNCTION prevent_decision_risk_mutation()" in source
    assert "CREATE TRIGGER trg_decision_risks_append_only" in source
    assert "BEFORE UPDATE OR DELETE ON decision_risks" in source
    assert "DROP TRIGGER IF EXISTS trg_decision_risks_append_only ON decision_risks" in source
    assert "DROP FUNCTION IF EXISTS prevent_decision_risk_mutation()" in source


def test_decision_risk_treatment_migration_declares_forward_only_append_only_transitions() -> None:
    source = TRANSITION_MIGRATION.read_text(encoding="utf-8")

    assert "decision_risk_treatment_transitions" in source
    assert "from_treatment = 'OPEN'" in source
    assert "to_treatment IN ('ACCEPTED', 'MITIGATED')" in source
    assert "from_treatment = 'ACCEPTED'" in source
    assert "to_treatment = 'MITIGATED'" in source
    assert "CREATE FUNCTION prevent_decision_risk_treatment_transition_mutation()" in source
    assert "BEFORE UPDATE OR DELETE ON decision_risk_treatment_transitions" in source

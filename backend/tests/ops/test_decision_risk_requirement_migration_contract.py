from pathlib import Path

MIGRATION = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "20260824_0059_create_decision_risk_requirement_links.py"
)


def test_risk_requirement_link_migration_is_append_only_and_tenant_scoped() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert '"decision_risk_requirement_links"' in source
    assert '"tenant_id", "risk_id"' in source
    assert '"tenant_id", "requirement_id"' in source
    assert "CREATE TRIGGER trg_decision_risk_links_append_only" in source
    assert "BEFORE UPDATE OR DELETE ON decision_risk_requirement_links" in source
    assert "DROP TRIGGER IF EXISTS trg_decision_risk_links_append_only" in source
    assert "DROP FUNCTION IF EXISTS prevent_decision_risk_link_mutation()" in source

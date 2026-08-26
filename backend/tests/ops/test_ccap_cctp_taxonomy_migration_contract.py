from pathlib import Path

MIGRATION = Path(__file__).parents[2] / "alembic/versions/20260826_0066_ccap_cctp_risk_taxonomy.py"


def test_ccap_cctp_taxonomy_migration_is_head_and_reversible() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "20260826_0066"' in source
    assert 'down_revision = "20260826_0065"' in source
    assert "def upgrade()" in source
    assert "def downgrade()" in source
    for category in (
        "CCAP_PENALTIES",
        "CCAP_RETENTION_GUARANTEE",
        "CCAP_GUARANTEE",
        "CCAP_INSURANCE",
        "CCTP_VARIANTS",
        "CCAP_SUBCONTRACTING",
        "CCAP_QUALIFICATIONS",
    ):
        assert category in source
    assert "CONTRACT_RISK_SIGNAL" in source

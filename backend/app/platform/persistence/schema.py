"""Runtime schema compatibility contract."""

# Bump this value whenever a migration becomes the supported runtime head.
# Tests compare it with Alembic's actual script graph to prevent silent drift.
EXPECTED_ALEMBIC_HEAD = "20260824_0058"

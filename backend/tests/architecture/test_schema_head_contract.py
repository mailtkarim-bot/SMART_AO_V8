from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.platform.persistence.schema import EXPECTED_ALEMBIC_HEAD


@pytest.mark.architecture
def test_runtime_schema_head_matches_alembic_script_graph() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    config = Config(str(repository_root / "backend" / "alembic.ini"))

    script_directory = ScriptDirectory.from_config(config)

    assert script_directory.get_current_head() == EXPECTED_ALEMBIC_HEAD

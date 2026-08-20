from __future__ import annotations

import os
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = os.getenv("SMART_AO_TEST_DATABASE_URL") or (
    "postgresql+psycopg://"
    + "smart_ao"
    + ":"
    + "smart_ao"
    + "@127.0.0.1:5432/smart_ao"
)

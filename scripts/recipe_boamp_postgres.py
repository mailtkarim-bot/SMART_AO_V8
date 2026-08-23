#!/usr/bin/env python3
"""Run the PostgreSQL recipe for BOAMP migrations 0053 and 0054."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _REPO_ROOT / "backend"
_TARGET_REVISION = "20260823_0054"
_REQUIRED_TABLES = {
    "boamp_ingestion_runs",
    "boamp_opportunity_observations",
    "boamp_ingestion_observation_links",
    "boamp_opportunity_qualifications",
}
_REQUIRED_TRIGGERS = {
    "boamp_ingestion_runs_append_only",
    "boamp_observations_append_only",
    "boamp_ingestion_links_append_only",
    "boamp_qualifications_append_only",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply and verify SMART_AO BOAMP PostgreSQL migrations."
    )
    parser.add_argument("--database-url", default=os.environ.get("SMART_AO_DATABASE_URL"))
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply Alembic head before verification; without it, only inspect the current DB.",
    )
    parser.add_argument("--skip-tests", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.database_url or args.database_url.startswith("REPLACE_WITH_"):
        print("BOAMP PostgreSQL recipe refused: database URL is missing", file=sys.stderr)
        return 2
    try:
        if args.apply:
            _apply_migrations(database_url=args.database_url)
        verification = _verify_database(database_url=args.database_url)
        if not args.skip_tests:
            _run_db_tests(database_url=args.database_url)
            verification["tests"] = "passed"
        else:
            verification["tests"] = "skipped"
    except (OSError, subprocess.CalledProcessError, sa.exc.SQLAlchemyError, RuntimeError) as error:
        print(f"BOAMP PostgreSQL recipe failed: {type(error).__name__}", file=sys.stderr)
        return 1
    print(json.dumps({"recipe": "BOAMP_POSTGRES_0053_0054", **verification}, sort_keys=True))
    return 0


def _apply_migrations(*, database_url: str) -> None:
    environment = {**os.environ, "SMART_AO_DATABASE_URL": database_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def _verify_database(*, database_url: str) -> dict[str, object]:
    engine = sa.create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            revision = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
            tables = set(
                connection.scalars(
                    sa.text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = 'public' AND tablename LIKE 'boamp_%'"
                    )
                )
            )
            triggers = set(
                connection.scalars(
                    sa.text(
                        "SELECT tgname FROM pg_trigger "
                        "WHERE NOT tgisinternal AND tgname LIKE 'boamp_%_append_only'"
                    )
                )
            )
    finally:
        engine.dispose()
    missing_tables = sorted(_REQUIRED_TABLES - tables)
    missing_triggers = sorted(_REQUIRED_TRIGGERS - triggers)
    if revision != _TARGET_REVISION or missing_tables or missing_triggers:
        raise RuntimeError("BOAMP schema verification failed")
    return {
        "alembic_revision": revision,
        "tables": sorted(_REQUIRED_TABLES),
        "append_only_triggers": sorted(_REQUIRED_TRIGGERS),
    }


def _run_db_tests(*, database_url: str) -> None:
    environment = {**os.environ, "SMART_AO_DATABASE_URL": database_url}
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/infrastructure/test_boamp_observation_persistence.py",
            "tests/infrastructure/test_boamp_qualification_persistence.py",
            "tests/process/test_opportunity_event_bus_persistence.py",
            "-q",
        ],
        cwd=_BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())

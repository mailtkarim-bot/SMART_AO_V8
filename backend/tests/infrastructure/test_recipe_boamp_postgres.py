from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "recipe_boamp_postgres.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("recipe_boamp_postgres", _SCRIPT_PATH)
assert _SCRIPT_SPEC is not None and _SCRIPT_SPEC.loader is not None
recipe = importlib.util.module_from_spec(_SCRIPT_SPEC)
_SCRIPT_SPEC.loader.exec_module(recipe)


def test_recipe_refuses_missing_database_url(capsys) -> None:
    assert recipe.main([]) == 2
    captured = capsys.readouterr()
    assert "missing" in captured.err
    assert "postgresql://" not in captured.out + captured.err


def test_recipe_runs_both_boamp_persistence_suites(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(command)

    monkeypatch.setattr(recipe.subprocess, "run", fake_run)
    recipe._run_db_tests(database_url="postgresql://recipe-user:recipe-password@localhost/smart_ao")

    assert calls
    assert "tests/infrastructure/test_boamp_observation_persistence.py" in calls[0]
    assert "tests/infrastructure/test_boamp_qualification_persistence.py" in calls[0]


def test_recipe_prints_sanitized_success_verdict_without_db(capsys, monkeypatch) -> None:
    monkeypatch.setattr(
        recipe,
        "_verify_database",
        lambda **_kwargs: {"alembic_revision": "20260823_0054"},
    )

    assert (
        recipe.main(
            [
                "--database-url",
                "postgresql://recipe-user:recipe-password@localhost/smart_ao",
                "--skip-tests",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "BOAMP_POSTGRES_0053_0054" in captured.out
    assert "recipe-password" not in captured.out
    assert "recipe-password" not in captured.err
    assert "skipped" in captured.out

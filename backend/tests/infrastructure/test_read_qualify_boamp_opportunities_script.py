from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "read_qualify_boamp_opportunities.py"
)
_SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "read_qualify_boamp_opportunities", _SCRIPT_PATH
)
assert _SCRIPT_SPEC is not None and _SCRIPT_SPEC.loader is not None
read_script = importlib.util.module_from_spec(_SCRIPT_SPEC)
_SCRIPT_SPEC.loader.exec_module(read_script)


def _projection() -> SimpleNamespace:
    return SimpleNamespace(
        observation_id=uuid4(),
        source_notice_id="A-1",
        title="Réhabilitation école",
        publication_date="2026-08-20",
        response_deadline="2026-09-01T12:00:00+00:00",
        department_codes=("59",),
        market_types=("TRAVAUX",),
        source_status="EN_COURS",
        score_version="BOAMP_PUBLIC_V1",
        score=100,
        score_explanation={"score": 100},
        fingerprint_sha256="a" * 64,
    )


def test_read_projection_is_closed_and_does_not_expose_internal_identity(capsys) -> None:
    read_script._print_read_projection((_projection(),))

    output = capsys.readouterr().out
    assert "A-1" in output
    assert "tenant_id" not in output
    assert "actor_id" not in output
    assert "financial" not in output.lower()


def test_qualification_arguments_require_all_server_supplied_ids() -> None:
    args = SimpleNamespace(
        observation_id=uuid4(),
        actor_id=uuid4(),
        reason_code="RELEVANT_PUBLIC_SIGNAL",
        command_id=None,
        idempotency_key=uuid4(),
    )

    with pytest.raises(ValueError, match="required"):
        read_script._require_qualification_args(args)

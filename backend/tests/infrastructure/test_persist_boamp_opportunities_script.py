from __future__ import annotations

import importlib.util
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from app.modules.opportunity.application.boamp_ingestion import OpportunityCandidate

_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "persist_boamp_opportunities.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("persist_boamp_opportunities", _SCRIPT_PATH)
assert _SCRIPT_SPEC is not None and _SCRIPT_SPEC.loader is not None
persist_script = importlib.util.module_from_spec(_SCRIPT_SPEC)
_SCRIPT_SPEC.loader.exec_module(persist_script)

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


def _payload() -> dict[str, object]:
    candidate = OpportunityCandidate(
        source="BOAMP",
        source_notice_id="A-1",
        title="Réhabilitation école",
        publication_date=date(2026, 8, 20),
        response_deadline=NOW + timedelta(days=5),
        department_codes=("59",),
        market_types=("TRAVAUX",),
        source_status="EN_COURS",
    )
    return {
        "schema": "SMART_AO_OPPORTUNITY_INGESTION_REPORT_V1",
        "pages_read": 1,
        "truncated": False,
        "candidates": [{**candidate.snapshot(), "fingerprint_sha256": candidate.fingerprint()}],
    }


def test_persistence_script_accepts_only_valid_staging_projection() -> None:
    candidates = persist_script._read_candidates(_payload())

    assert len(candidates) == 1
    assert candidates[0].source_notice_id == "A-1"


def test_persistence_script_rejects_tampered_fingerprint_and_extra_fields() -> None:
    tampered = _payload()
    tampered["candidates"][0]["fingerprint_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="fingerprint"):
        persist_script._read_candidates(tampered)

    extra = _payload()
    extra["candidates"][0]["financial_amount"] = "100"
    with pytest.raises(ValueError, match="allowlist"):
        persist_script._read_candidates(extra)


def test_persistence_script_requires_the_closed_report_schema() -> None:
    invalid = _payload()
    invalid["schema"] = "OTHER"

    with pytest.raises(ValueError, match="schema"):
        persist_script._read_candidates(invalid)

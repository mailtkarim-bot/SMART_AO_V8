from __future__ import annotations

import importlib.util
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from app.modules.market_watch.application.ports import BoampNotice
from app.modules.opportunity.application.boamp_ingestion import (
    BoampOpportunityIngestionService,
    OpportunityIngestionLimitError,
)
from app.modules.opportunity.domain.watch_profile import WatchProfileCriteria

_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "ingest_boamp_opportunities.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("ingest_boamp_opportunities", _SCRIPT_PATH)
assert _SCRIPT_SPEC is not None and _SCRIPT_SPEC.loader is not None
ingest_boamp_opportunities = importlib.util.module_from_spec(_SCRIPT_SPEC)
_SCRIPT_SPEC.loader.exec_module(ingest_boamp_opportunities)

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)



class FakeBoampPort:
    def __init__(self, pages: dict[tuple[str, int], tuple[BoampNotice, ...]]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, int, int]] = []

    def search(self, *, text: str, limit: int = 20, offset: int = 0):
        self.calls.append((text, limit, offset))
        return self.pages.get((text, offset), ())


def _notice(
    notice_id: str,
    *,
    department: str = "59",
    deadline: datetime | None = NOW + timedelta(days=10),
    title: str = "Avis public",
) -> BoampNotice:
    return BoampNotice(
        notice_id=notice_id,
        title=title,
        publication_date=date(2026, 8, 20),
        response_deadline=deadline,
        department_codes=(department,),
        market_types=("TRAVAUX",),
        status="EN_COURS",
    )


def test_ingestion_is_bounded_filters_and_deduplicates() -> None:
    duplicate = _notice("A-1", title="Avis public")
    port = FakeBoampPort(
        {
            ("réhabilitation", 0): (
                duplicate,
                duplicate,
                _notice("EXCLUDED", department="62"),
                _notice("EXPIRED", deadline=NOW - timedelta(days=1)),
            )
        }
    )
    service = BoampOpportunityIngestionService(
        search_port=port,
        page_size=20,
        max_pages_per_keyword=2,
        max_results=20,
    )

    report = service.ingest(
        criteria=WatchProfileCriteria(
            keywords=(" Réhabilitation ",),
            included_departments=("59",),
            excluded_departments=("62",),
        ),
        now=NOW,
    )

    assert [candidate.source_notice_id for candidate in report.candidates] == ["A-1"]
    assert report.candidates[0].source == "BOAMP"
    assert len(report.candidates[0].fingerprint()) == 64
    assert report.pages_read == 1
    assert report.truncated is False
    assert port.calls == [("réhabilitation", 20, 0)]


def test_ingestion_reports_truncation_at_result_budget() -> None:
    port = FakeBoampPort(
        {
            ("construction", 0): (_notice("A-1"),),
            ("construction", 1): (_notice("A-2"),),
        }
    )

    report = BoampOpportunityIngestionService(
        search_port=port,
        page_size=1,
        max_pages_per_keyword=5,
        max_results=1,
    ).ingest(criteria=WatchProfileCriteria(keywords=("construction",)), now=NOW)

    assert [candidate.source_notice_id for candidate in report.candidates] == ["A-1"]
    assert report.truncated is True
    assert report.pages_read == 1


def test_ingestion_rejects_empty_keywords_and_excessive_keyword_budget() -> None:
    with pytest.raises(ValueError, match="at least one"):
        BoampOpportunityIngestionService(search_port=FakeBoampPort({})).ingest(
            criteria=WatchProfileCriteria(), now=NOW
        )
    with pytest.raises(OpportunityIngestionLimitError):
        BoampOpportunityIngestionService(
            search_port=FakeBoampPort({}), max_keywords=1
        ).ingest(
            criteria=WatchProfileCriteria(keywords=("one", "two")), now=NOW
        )


def test_script_writes_closed_reproducible_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_port = FakeBoampPort({("construction", 0): (_notice("A-1"),)})
    monkeypatch.setattr(ingest_boamp_opportunities, "BoampReadOnlySearch", lambda **_: fake_port)
    output = tmp_path / "report.json"

    result = ingest_boamp_opportunities.main(
        [
            "--keyword",
            "construction",
            "--now",
            "2026-08-23T12:00:00Z",
            "--output",
            str(output),
        ]
    )

    assert result == 0
    payload = output.read_text(encoding="utf-8")
    assert '"schema": "SMART_AO_OPPORTUNITY_INGESTION_REPORT_V1"' in payload
    assert '"source": "BOAMP"' in payload
    assert "A-1" in payload
    assert "tenant_id" not in payload
    assert "financial" not in payload.lower()

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.modules.market_watch.application.ports import BoampNotice
from app.modules.opportunity.application.boamp_ingestion import OpportunityCandidate
from app.modules.opportunity.application.boamp_scoring import (
    SCORING_VERSION,
    BoampOpportunityScoringService,
)
from app.modules.opportunity.domain.watch_profile import WatchProfileCriteria

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


def _candidate(*, title: str, department: str = "59", status: str = "EN_COURS"):
    return OpportunityCandidate(
        source="BOAMP",
        source_notice_id="A-1",
        title=title,
        publication_date=date(2026, 8, 20),
        response_deadline=NOW + timedelta(days=10),
        department_codes=(department,),
        market_types=("TRAVAUX",),
        source_status=status,
    )


def test_scoring_is_explainable_bounded_and_deterministic() -> None:
    candidate = _candidate(title="Réhabilitation d’une école publique")
    criteria = WatchProfileCriteria(
        keywords=("réhabilitation",),
        included_departments=("59",),
    )
    service = BoampOpportunityScoringService()

    first = service.score(candidate=candidate, criteria=criteria, now=NOW)
    second = service.score(candidate=candidate, criteria=criteria, now=NOW)

    assert first.version == SCORING_VERSION
    assert first.score == 100
    assert first.snapshot() == second.snapshot()
    assert len(first.explanation_sha256) == 64
    assert {factor.code for factor in first.factors} == {
        "TITLE_KEYWORD_MATCH",
        "INCLUDED_DEPARTMENT_MATCH",
        "ACTIVE_SOURCE_STATUS",
        "FUTURE_RESPONSE_DEADLINE",
    }


def test_scoring_exposes_negative_evidence_without_financial_inference() -> None:
    candidate = _candidate(title="Avis public", department="62", status="CLOSED")
    criteria = WatchProfileCriteria(
        keywords=("réhabilitation",),
        included_departments=("59",),
    )

    result = BoampOpportunityScoringService().score(
        candidate=candidate, criteria=criteria, now=NOW
    )

    assert result.score == 10
    assert all(0 <= factor.points <= 50 for factor in result.factors)
    assert all("price" not in factor.explanation.lower() for factor in result.factors)
    assert "financial" not in str(result.snapshot()).lower()


def test_ingested_notice_can_be_scored_without_persisting_rich_payload() -> None:
    notice = BoampNotice(
        notice_id="A-2",
        title="Maintenance bâtiment",
        publication_date=date(2026, 8, 20),
        response_deadline=NOW + timedelta(days=2),
        department_codes=("59",),
        market_types=("TRAVAUX",),
        status="PUBLIE",
    )
    candidate = OpportunityCandidate(
        source="BOAMP",
        source_notice_id=notice.notice_id,
        title=notice.title,
        publication_date=notice.publication_date,
        response_deadline=notice.response_deadline,
        department_codes=notice.department_codes,
        market_types=notice.market_types,
        source_status=notice.status,
    )
    result = BoampOpportunityScoringService().score(
        candidate=candidate,
        criteria=WatchProfileCriteria(keywords=("maintenance",)),
        now=NOW,
    )

    assert result.score == 75
    assert "donnees" not in str(result.snapshot()).lower()
    assert "gestion" not in str(result.snapshot()).lower()

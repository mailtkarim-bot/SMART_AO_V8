"""Explainable, non-financial scoring for public BOAMP candidates."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from app.modules.opportunity.application.boamp_ingestion import OpportunityCandidate
from app.modules.opportunity.domain.watch_profile import WatchProfileCriteria

SCORING_VERSION = "BOAMP_PUBLIC_V1"


@dataclass(frozen=True, slots=True)
class ScoreFactor:
    code: str
    points: int
    matched: bool
    explanation: str

    def snapshot(self) -> dict[str, object]:
        return {
            "code": self.code,
            "explanation": self.explanation,
            "matched": self.matched,
            "points": self.points,
        }


@dataclass(frozen=True, slots=True)
class ExplainableOpportunityScore:
    version: str
    score: int
    factors: tuple[ScoreFactor, ...]
    explanation_sha256: str

    def snapshot(self) -> dict[str, object]:
        return {
            "explanation_sha256": self.explanation_sha256,
            "factors": [factor.snapshot() for factor in self.factors],
            "score": self.score,
            "version": self.version,
        }


class BoampOpportunityScoringService:
    """Score only public candidate signals; never infer financial suitability."""

    def score(
        self,
        *,
        candidate: OpportunityCandidate,
        criteria: WatchProfileCriteria,
        now: datetime,
    ) -> ExplainableOpportunityScore:
        current = _as_utc(now)
        normalized_title = (candidate.title or "").casefold()
        matched_keywords = tuple(
            keyword for keyword in criteria.keywords if keyword.casefold() in normalized_title
        )
        factors = (
            ScoreFactor(
                code="TITLE_KEYWORD_MATCH",
                points=50 if matched_keywords else 0,
                matched=bool(matched_keywords),
                explanation=(
                    f"{len(matched_keywords)} profil keyword(s) found in the public title"
                    if matched_keywords
                    else "No profile keyword found in the public title"
                ),
            ),
            ScoreFactor(
                code="INCLUDED_DEPARTMENT_MATCH",
                points=25
                if set(candidate.department_codes).intersection(criteria.included_departments)
                else 0,
                matched=bool(
                    set(candidate.department_codes).intersection(criteria.included_departments)
                ),
                explanation=(
                    "The public notice has an included department"
                    if set(candidate.department_codes).intersection(criteria.included_departments)
                    else "No included department was configured or matched"
                ),
            ),
            ScoreFactor(
                code="ACTIVE_SOURCE_STATUS",
                points=15 if _is_active_status(candidate.source_status) else 0,
                matched=_is_active_status(candidate.source_status),
                explanation=(
                    "The source status is allowlisted as active"
                    if _is_active_status(candidate.source_status)
                    else "The source status is absent or not allowlisted as active"
                ),
            ),
            ScoreFactor(
                code="FUTURE_RESPONSE_DEADLINE",
                points=10
                if candidate.response_deadline is not None
                and candidate.response_deadline >= current
                else 0,
                matched=(
                    candidate.response_deadline is not None
                    and candidate.response_deadline >= current
                ),
                explanation=(
                    "A non-expired public response deadline is available"
                    if candidate.response_deadline is not None
                    and candidate.response_deadline >= current
                    else "No future public response deadline is available"
                ),
            ),
        )
        score = sum(factor.points for factor in factors)
        explanation = json.dumps(
            {
                "factors": [factor.snapshot() for factor in factors],
                "score": score,
                "version": SCORING_VERSION,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        return ExplainableOpportunityScore(
            version=SCORING_VERSION,
            score=score,
            factors=factors,
            explanation_sha256=hashlib.sha256(explanation.encode("utf-8")).hexdigest(),
        )


def _is_active_status(status: str | None) -> bool:
    return (status or "").strip().upper() in {"ACTIVE", "EN_COURS", "OPEN", "PUBLIE"}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

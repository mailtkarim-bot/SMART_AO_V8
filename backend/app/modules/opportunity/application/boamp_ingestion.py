"""Bounded BOAMP ingestion into a non-persistent opportunity staging report."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.modules.market_watch.application.ports import BoampNotice, PublicNoticeSearchPort
from app.modules.opportunity.domain.watch_profile import WatchProfileCriteria


class OpportunityIngestionLimitError(ValueError):
    """The requested deterministic ingestion exceeds the configured safety budget."""


@dataclass(frozen=True, slots=True)
class OpportunityCandidate:
    source: str
    source_notice_id: str
    title: str | None
    publication_date: date | None
    response_deadline: datetime | None
    department_codes: tuple[str, ...]
    market_types: tuple[str, ...]
    source_status: str | None

    def snapshot(self) -> dict[str, object]:
        return {
            "department_codes": list(self.department_codes),
            "market_types": list(self.market_types),
            "publication_date": self.publication_date.isoformat()
            if self.publication_date is not None
            else None,
            "response_deadline": self.response_deadline.isoformat()
            if self.response_deadline is not None
            else None,
            "source": self.source,
            "source_notice_id": self.source_notice_id,
            "source_status": self.source_status,
            "title": self.title,
        }

    def fingerprint(self) -> str:
        canonical = json.dumps(
            self.snapshot(), ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class OpportunityIngestionReport:
    candidates: tuple[OpportunityCandidate, ...]
    searched_keywords: tuple[str, ...]
    pages_read: int
    truncated: bool


class BoampOpportunityIngestionService:
    """Read BOAMP through a port and emit bounded, public opportunity candidates.

    This service deliberately does not persist, score, qualify, create a Case, or
    expose the BOAMP rich ``donnees``/``gestion`` objects.
    """

    def __init__(
        self,
        *,
        search_port: PublicNoticeSearchPort,
        page_size: int = 20,
        max_pages_per_keyword: int = 5,
        max_keywords: int = 8,
        max_results: int = 200,
    ) -> None:
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        if not 1 <= max_pages_per_keyword <= 10:
            raise ValueError("max_pages_per_keyword must be between 1 and 10")
        if not 1 <= max_keywords <= 32:
            raise ValueError("max_keywords must be between 1 and 32")
        if not 1 <= max_results <= 500:
            raise ValueError("max_results must be between 1 and 500")
        self._search_port = search_port
        self._page_size = page_size
        self._max_pages_per_keyword = max_pages_per_keyword
        self._max_keywords = max_keywords
        self._max_results = max_results

    def ingest(
        self,
        *,
        criteria: WatchProfileCriteria,
        now: datetime,
    ) -> OpportunityIngestionReport:
        if not criteria.keywords:
            raise ValueError("BOAMP ingestion requires at least one profile keyword")
        if len(criteria.keywords) > self._max_keywords:
            raise OpportunityIngestionLimitError(
                "BOAMP keyword count exceeds the ingestion request budget"
            )
        current = _as_utc(now)
        candidates: dict[str, OpportunityCandidate] = {}
        pages_read = 0
        truncated = False
        for keyword in criteria.keywords:
            for page_number in range(self._max_pages_per_keyword):
                if len(candidates) >= self._max_results:
                    truncated = True
                    break
                notices = self._search_port.search(
                    text=keyword,
                    limit=min(self._page_size, self._max_results - len(candidates)),
                    offset=page_number * self._page_size,
                )
                pages_read += 1
                for notice in notices:
                    candidate = _candidate_from_notice(notice)
                    if not _matches_criteria(candidate, criteria=criteria, now=current):
                        continue
                    existing = candidates.get(candidate.source_notice_id)
                    if existing is None or candidate.fingerprint() < existing.fingerprint():
                        candidates[candidate.source_notice_id] = candidate
                if len(notices) < self._page_size:
                    break
                if page_number == self._max_pages_per_keyword - 1:
                    truncated = True
            if truncated and len(candidates) >= self._max_results:
                break
        return OpportunityIngestionReport(
            candidates=tuple(candidates[key] for key in sorted(candidates)),
            searched_keywords=criteria.keywords,
            pages_read=pages_read,
            truncated=truncated,
        )


def _candidate_from_notice(notice: BoampNotice) -> OpportunityCandidate:
    notice_id = " ".join(notice.notice_id.split())
    title = " ".join(notice.title.split()) if notice.title else None
    if title is not None:
        title = title[:500]
    return OpportunityCandidate(
        source="BOAMP",
        source_notice_id=notice_id,
        title=title,
        publication_date=notice.publication_date,
        response_deadline=_as_utc(notice.response_deadline)
        if notice.response_deadline is not None
        else None,
        department_codes=tuple(sorted({code.strip().upper() for code in notice.department_codes})),
        market_types=tuple(sorted({market.strip().upper() for market in notice.market_types})),
        source_status=" ".join(notice.status.split()) if notice.status else None,
    )


def _matches_criteria(
    candidate: OpportunityCandidate,
    *,
    criteria: WatchProfileCriteria,
    now: datetime,
) -> bool:
    departments = set(candidate.department_codes)
    if criteria.included_departments and not departments.intersection(
        criteria.included_departments
    ):
        return False
    if departments.intersection(criteria.excluded_departments):
        return False
    return not (
        candidate.response_deadline is not None and candidate.response_deadline < now
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

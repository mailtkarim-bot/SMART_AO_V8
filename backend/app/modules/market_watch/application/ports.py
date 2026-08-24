"""Pure ports and facts for read-only public procurement watch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BoampNotice:
    notice_id: str
    title: str | None
    publication_date: date | None
    response_deadline: datetime | None
    department_codes: tuple[str, ...]
    market_types: tuple[str, ...]
    status: str | None


class PublicNoticeSearchPort(Protocol):
    def search(self, *, text: str, limit: int = 20, offset: int = 0) -> tuple[BoampNotice, ...]: ...

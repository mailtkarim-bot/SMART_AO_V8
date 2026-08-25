"""Application service for bounded, read-only public notice search."""

from __future__ import annotations

from app.modules.market_watch.application.ports import BoampNotice, PublicNoticeSearchPort


class PublicNoticeSearchService:
    """Delegates bounded public search without persisting or enriching results."""

    def __init__(self, *, search_port: PublicNoticeSearchPort) -> None:
        self._search_port = search_port

    def search(self, *, text: str, limit: int = 20, offset: int = 0) -> tuple[BoampNotice, ...]:
        return self._search_port.search(text=text, limit=limit, offset=offset)

"""Application port for a safe, file-based submission deadline calendar export."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID


class SubmissionDeadlineCalendarPort(Protocol):
    def render_deadline(
        self,
        *,
        case_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        stamp: datetime,
    ) -> bytes:
        """Render an ICS event without contacting a calendar provider."""
        ...

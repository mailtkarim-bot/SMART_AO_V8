"""Optional RFC 5545 calendar export for a submission deadline."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.modules.submission.application.calendar import SubmissionDeadlineCalendarPort


class IcsCalendarUnavailable(RuntimeError):
    """The optional calendar renderer is unavailable or rejected the input."""


class IcsSubmissionDeadlineCalendar(SubmissionDeadlineCalendarPort):
    """Render one private, non-financial deadline event without calendar sync."""

    def __init__(self, *, icalendar_module: Any | None = None) -> None:
        self._icalendar = icalendar_module or _load_icalendar_module()

    def render_deadline(
        self,
        *,
        case_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        stamp: datetime,
    ) -> bytes:
        start = _as_utc(starts_at)
        end = _as_utc(ends_at)
        created = _as_utc(stamp)
        if end <= start:
            raise ValueError("calendar deadline end must be after start")

        calendar = self._icalendar.Calendar()
        calendar.add("prodid", "-//SMART AO V8//Submission deadline//FR")
        calendar.add("version", "2.0")
        event = self._icalendar.Event()
        event.add("uid", _event_uid(case_id=case_id, starts_at=start))
        event.add("dtstamp", created)
        event.add("dtstart", start)
        event.add("dtend", end)
        event.add("summary", "Échéance du dossier d’appel d’offres")
        event.add(
            "description",
            "Échéance enregistrée dans SMART AO. Aucun document ni montant n’est inclus.",
        )
        calendar.add_component(event)
        try:
            rendered = calendar.to_ical()
        except Exception as exc:
            raise IcsCalendarUnavailable("ICS calendar rendering failed") from exc
        if not isinstance(rendered, bytes):
            raise IcsCalendarUnavailable("ICS calendar renderer returned invalid data")
        return rendered


def _load_icalendar_module() -> Any:
    try:
        import icalendar
    except ImportError as exc:
        raise RuntimeError("calendar extra is not installed") from exc
    return icalendar


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("calendar datetimes must be timezone-aware")
    return value.astimezone(UTC)


def _event_uid(*, case_id: UUID, starts_at: datetime) -> str:
    seed = f"{case_id}:{starts_at.isoformat()}".encode()
    digest = hashlib.sha256(seed).hexdigest()
    return f"{digest}@smart-ao.local"

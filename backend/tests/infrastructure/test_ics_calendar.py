from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.modules.submission.infrastructure.ics_calendar import (
    IcsSubmissionDeadlineCalendar,
)


def test_ics_export_is_deterministic_and_contains_no_financial_payload() -> None:
    renderer = IcsSubmissionDeadlineCalendar()
    case_id = uuid4()
    start = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    stamp = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)

    first = renderer.render_deadline(
        case_id=case_id,
        starts_at=start,
        ends_at=end,
        stamp=stamp,
    )
    second = renderer.render_deadline(
        case_id=case_id,
        starts_at=start,
        ends_at=end,
        stamp=stamp,
    )

    assert first == second
    text = first.decode("utf-8")
    assert "BEGIN:VCALENDAR" in text
    assert "BEGIN:VEVENT" in text
    assert "DTSTART:20260901T100000Z" in text
    assert "DTEND:20260901T110000Z" in text
    assert "SUMMARY:" in text
    assert str(case_id) not in text
    assert "montant" not in text.lower()
    assert "document" in text.lower()


def test_ics_export_rejects_naive_or_reversed_datetimes() -> None:
    renderer = IcsSubmissionDeadlineCalendar()
    aware = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="timezone-aware"):
        renderer.render_deadline(
            case_id=uuid4(),
            starts_at=aware.replace(tzinfo=None),
            ends_at=aware + timedelta(hours=1),
            stamp=aware,
        )
    with pytest.raises(ValueError, match="after start"):
        renderer.render_deadline(
            case_id=uuid4(),
            starts_at=aware,
            ends_at=aware,
            stamp=aware,
        )

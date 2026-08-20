from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.modules.dce.application.queries import CaseDceReadingAvailability
from app.modules.dce.infrastructure.case_dce_reading_reader import (
    SqlAlchemyCaseDceReadingReader,
    _positive_int,
    _safe_document_family,
    _safe_locator_token,
    _source_locator_label,
)

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


class _ScalarSequenceSession:
    def __init__(self, *values):
        self.values = list(values)

    def scalar(self, statement):
        return self.values.pop(0)


def test_reader_returns_broken_reference_without_leaking_dce_data():
    case = SimpleNamespace(
        id=uuid4(), title="Affaire", lifecycle="ACTIVE", commercial_stage="ANALYSIS",
        dce_freshness="REVIEW_REQUIRED", applicable_dce_version_id=uuid4(),
    )
    reader = SqlAlchemyCaseDceReadingReader(_ScalarSequenceSession(case, None))

    lookup = reader.get(tenant_id=uuid4(), case_id=case.id)

    assert lookup is not None
    assert lookup.availability is CaseDceReadingAvailability.DCE_REFERENCE_BROKEN
    assert lookup.reading is None
    assert lookup.work_label == "Affaire"


@pytest.mark.parametrize(
    ("classification", "expected"),
    [
        (family, family)
        for family in ("RC", "CCAP", "CCTP", "AE", "BPU", "DPGF", "PLAN", "ANNEX", "RECTIFICATION")
    ]
    + [(None, "SOURCE_UNCLASSIFIED"), ("UNKNOWN", "SOURCE_UNCLASSIFIED")],
)
def test_safe_document_family_exposes_only_closed_vocabulary(classification, expected):
    assert _safe_document_family(classification) == expected


@pytest.mark.parametrize(
    ("locator", "family", "expected"),
    [
        ({"kind": "pdf_page", "page": 3}, "CCTP", "CCTP · page 3"),
        ({"kind": "docx_paragraph", "paragraph": 4}, "AE", "AE · paragraphe 4"),
        ({"kind": "text_line", "line": 8}, "RC", "RC · ligne 8"),
        ({"kind": "xlsx_cell", "sheet": "BPU", "cell": "C12"}, "BPU", "BPU · cellule BPU!C12"),
        ({"kind": "pdf_page", "page": 0}, "CCTP", "Source localisée"),
        ({"kind": "pdf_page", "page": True}, "CCTP", "Source localisée"),
        ({"kind": "xlsx_cell", "sheet": "bad\n", "cell": "C12"}, "BPU", "Source localisée"),
        ({"kind": "xlsx_cell", "sheet": "BPU", "cell": "C" * 17}, "BPU", "Source localisée"),
        (None, "SOURCE_UNCLASSIFIED", "Source localisée"),
    ],
)
def test_source_locator_label_is_bounded_and_human_readable(locator, family, expected):
    assert _source_locator_label(document_family=family, locator_json=locator) == expected


@pytest.mark.parametrize("value", [1, 10, 999])
def test_positive_int_accepts_only_positive_integers(value):
    assert _positive_int(value) is True


@pytest.mark.parametrize("value", [0, -1, True, False, "1", None])
def test_positive_int_rejects_invalid_values(value):
    assert _positive_int(value) is False


@pytest.mark.parametrize("value", ["sheet", "C12", "x" * 80])
def test_safe_locator_token_accepts_bounded_clean_text(value):
    assert _safe_locator_token(value, maximum_length=80) is True


@pytest.mark.parametrize("value", [None, "", " ", "x" * 81, "line\n", "line\r"])
def test_safe_locator_token_rejects_untrusted_text(value):
    assert _safe_locator_token(value, maximum_length=80) is False


def test_reader_counters_classify_all_closed_outcomes():
    requirements = [
        SimpleNamespace(confirmation_outcome="CONFIRMED"),
        SimpleNamespace(confirmation_outcome="REVIEW_REQUIRED"),
        SimpleNamespace(confirmation_outcome="NOT_APPLICABLE"),
        SimpleNamespace(confirmation_outcome="PENDING_HUMAN_CONFIRMATION"),
    ]

    counters = SqlAlchemyCaseDceReadingReader._counters(requirements)

    assert counters.total == 4
    assert counters.confirmed == 1
    assert counters.review_required == 1
    assert counters.not_applicable == 1
    assert counters.pending_human_confirmation == 1

from __future__ import annotations

import pytest
from app.modules.opportunity.domain.watch_profile import (
    BuyerType,
    ProjectType,
    ResponseMode,
    WatchProfileCriteria,
    WatchProfileValidationError,
    normalize_profile_name,
)


def test_profile_name_and_keywords_are_normalized_deterministically() -> None:
    criteria = WatchProfileCriteria(
        keywords=("  Réhabilitation  ", "Gros   œuvre"),
        project_types=(ProjectType.REFURBISHMENT,),
        buyer_types=(BuyerType.PUBLIC_BUYER,),
        included_departments=("59", "2a"),
        response_modes=(ResponseMode.SOLO,),
    )

    assert normalize_profile_name("  Gros   œuvre — Nord  ") == "Gros œuvre — Nord"
    assert criteria.keywords == ("gros œuvre", "réhabilitation")
    assert criteria.included_departments == ("2A", "59")
    assert criteria.snapshot() == {
        "buyer_types": ["PUBLIC_BUYER"],
        "excluded_departments": [],
        "included_departments": ["2A", "59"],
        "keywords": ["gros œuvre", "réhabilitation"],
        "max_radius_km": None,
        "project_types": ["REFURBISHMENT"],
        "require_qualification": False,
        "response_modes": ["SOLO"],
        "visit_preference": "ANY",
    }


def test_profile_rejects_duplicate_or_conflicting_criteria() -> None:
    with pytest.raises(WatchProfileValidationError, match="duplicates"):
        WatchProfileCriteria(keywords=("travaux", "TRAVAUX"))

    with pytest.raises(WatchProfileValidationError, match="both included and excluded"):
        WatchProfileCriteria(included_departments=("59",), excluded_departments=("59",))


def test_profile_rejects_unknown_values_and_out_of_range_radius() -> None:
    with pytest.raises(ValueError):
        WatchProfileCriteria(project_types=("UNKNOWN",))  # type: ignore[arg-type]

    with pytest.raises(WatchProfileValidationError, match="between"):
        WatchProfileCriteria(max_radius_km=1_001)

    with pytest.raises(WatchProfileValidationError, match="invalid"):
        WatchProfileCriteria(included_departments=("FR-59",))


def test_profile_rejects_unbounded_keywords_and_name() -> None:
    with pytest.raises(WatchProfileValidationError, match="too many keywords"):
        WatchProfileCriteria(keywords=tuple(f"keyword-{index}" for index in range(33)))

    with pytest.raises(WatchProfileValidationError, match="too long"):
        normalize_profile_name("x" * 121)

    with pytest.raises(WatchProfileValidationError, match="required"):
        normalize_profile_name("  \n\t")

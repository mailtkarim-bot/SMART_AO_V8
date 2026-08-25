"""Pure domain rules for a patron opportunity watch profile."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class WatchProfileValidationError(ValueError):
    """Raised when a watch profile violates its closed domain contract."""


class WatchProfileState(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"


class ProjectType(StrEnum):
    NEW_BUILD = "NEW_BUILD"
    REFURBISHMENT = "REFURBISHMENT"
    OCCUPIED_SITE = "OCCUPIED_SITE"
    TERTIARY = "TERTIARY"
    HEALTHCARE = "HEALTHCARE"
    HOUSING = "HOUSING"
    INDUSTRY = "INDUSTRY"
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    HERITAGE = "HERITAGE"


class BuyerType(StrEnum):
    PUBLIC_BUYER = "PUBLIC_BUYER"
    PRIVATE_BUYER = "PRIVATE_BUYER"
    SOCIAL_LANDLORD = "SOCIAL_LANDLORD"
    LOCAL_AUTHORITY = "LOCAL_AUTHORITY"
    HEALTHCARE_BUYER = "HEALTHCARE_BUYER"
    INDUSTRIAL_BUYER = "INDUSTRIAL_BUYER"
    KNOWN_CLIENT = "KNOWN_CLIENT"


class ResponseMode(StrEnum):
    SOLO = "SOLO"
    CONSORTIUM = "CONSORTIUM"
    SUBCONTRACTING = "SUBCONTRACTING"


_DEPARTMENT_PATTERN: Final = re.compile(r"^[0-9A-Z]{2,3}$")
_MAX_KEYWORDS = 32
_MAX_KEYWORD_LENGTH = 80
_MAX_DEPARTMENTS = 101
_MAX_PROFILE_NAME_LENGTH = 120


@dataclass(frozen=True, slots=True)
class WatchProfileCriteria:
    """Allowlisted, deterministic preferences owned by a patron tenant."""

    keywords: tuple[str, ...] = ()
    project_types: tuple[ProjectType, ...] = ()
    buyer_types: tuple[BuyerType, ...] = ()
    included_departments: tuple[str, ...] = ()
    excluded_departments: tuple[str, ...] = ()
    max_radius_km: int | None = None
    response_modes: tuple[ResponseMode, ...] = ()
    require_qualification: bool = False
    visit_preference: str = "ANY"

    def __post_init__(self) -> None:
        normalized_keywords = _normalize_keywords(self.keywords)
        normalized_project_types = _normalize_enum_values(
            self.project_types, ProjectType, "project_types"
        )
        normalized_buyer_types = _normalize_enum_values(self.buyer_types, BuyerType, "buyer_types")
        normalized_response_modes = _normalize_enum_values(
            self.response_modes, ResponseMode, "response_modes"
        )
        normalized_included = _normalize_departments(self.included_departments)
        normalized_excluded = _normalize_departments(self.excluded_departments)
        if set(normalized_included) & set(normalized_excluded):
            raise WatchProfileValidationError("department cannot be both included and excluded")
        if self.max_radius_km is not None and not 1 <= self.max_radius_km <= 1_000:
            raise WatchProfileValidationError("max_radius_km must be between 1 and 1000")
        if self.visit_preference not in {"ANY", "PRIORITIZE", "REQUIRE"}:
            raise WatchProfileValidationError("visit_preference is not supported")
        _ensure_unique(normalized_project_types, "project_types")
        _ensure_unique(normalized_buyer_types, "buyer_types")
        _ensure_unique(normalized_response_modes, "response_modes")
        object.__setattr__(self, "keywords", normalized_keywords)
        object.__setattr__(self, "project_types", normalized_project_types)
        object.__setattr__(self, "buyer_types", normalized_buyer_types)
        object.__setattr__(self, "response_modes", normalized_response_modes)
        object.__setattr__(self, "included_departments", normalized_included)
        object.__setattr__(self, "excluded_departments", normalized_excluded)

    def snapshot(self) -> dict[str, object]:
        """Return a stable non-documentary representation for hashing/persistence."""

        return {
            "buyer_types": [value.value for value in self.buyer_types],
            "excluded_departments": list(self.excluded_departments),
            "included_departments": list(self.included_departments),
            "keywords": list(self.keywords),
            "max_radius_km": self.max_radius_km,
            "project_types": [value.value for value in self.project_types],
            "require_qualification": self.require_qualification,
            "response_modes": [value.value for value in self.response_modes],
            "visit_preference": self.visit_preference,
        }


def normalize_profile_name(name: str) -> str:
    normalized = " ".join(name.split())
    if not normalized:
        raise WatchProfileValidationError("profile name is required")
    if len(normalized) > _MAX_PROFILE_NAME_LENGTH:
        raise WatchProfileValidationError("profile name is too long")
    return normalized


def _normalize_keywords(values: tuple[str, ...]) -> tuple[str, ...]:
    if len(values) > _MAX_KEYWORDS:
        raise WatchProfileValidationError("too many keywords")
    normalized = tuple(" ".join(value.split()).casefold() for value in values)
    if any(not value or len(value) > _MAX_KEYWORD_LENGTH for value in normalized):
        raise WatchProfileValidationError("keyword is empty or too long")
    _ensure_unique(normalized, "keywords")
    return tuple(sorted(normalized))


def _normalize_enum_values[EnumT: StrEnum](
    values: tuple[EnumT | str, ...], enum_type: type[EnumT], field: str
) -> tuple[EnumT, ...]:
    try:
        normalized = tuple(enum_type(value) for value in values)
    except (TypeError, ValueError) as error:
        raise WatchProfileValidationError(f"{field} contains an unsupported value") from error
    return normalized


def _normalize_departments(values: tuple[str, ...]) -> tuple[str, ...]:
    if len(values) > _MAX_DEPARTMENTS:
        raise WatchProfileValidationError("too many departments")
    normalized = tuple(value.strip().upper() for value in values)
    if any(not _DEPARTMENT_PATTERN.fullmatch(value) for value in normalized):
        raise WatchProfileValidationError("department code is invalid")
    _ensure_unique(normalized, "departments")
    return tuple(sorted(normalized))


def _ensure_unique(values: tuple[object, ...], field: str) -> None:
    if len(values) != len(set(values)):
        raise WatchProfileValidationError(f"{field} must not contain duplicates")

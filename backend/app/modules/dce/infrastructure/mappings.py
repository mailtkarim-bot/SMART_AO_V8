from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.modules.dce.domain.dce_version import (
    AnalysisReadiness,
    ClassificationReadiness,
    DceIntegrity,
    DceLifecycle,
    DceVersion,
)


@dataclass(frozen=True, slots=True)
class DceVersionPersistenceState:
    """Explicit persistence representation of the DCE domain state enums."""

    lifecycle: str
    integrity: str
    classification_readiness: str
    analysis_readiness: str


def to_dce_version_persistence_state(version: DceVersion) -> DceVersionPersistenceState:
    """Map domain enum values to the CHECK-constrained persistence strings."""

    return DceVersionPersistenceState(
        lifecycle=_enum_value(version.lifecycle, DceLifecycle),
        integrity=_enum_value(version.integrity, DceIntegrity),
        classification_readiness=_enum_value(
            version.classification_readiness, ClassificationReadiness
        ),
        analysis_readiness=_enum_value(version.analysis_readiness, AnalysisReadiness),
    )


def _enum_value(value: object, expected_type: type[StrEnum]) -> str:
    if not isinstance(value, expected_type):
        raise TypeError(f"expected {expected_type.__name__}, got {type(value).__name__}")
    return value.value

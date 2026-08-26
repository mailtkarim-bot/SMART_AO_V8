"""Read ports and closed projections for DCE application views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ConsultationProjection:
    """Read-only Consultation situation safe for the first public API path."""

    id: UUID
    buyer_legal_name: str
    external_reference: str | None
    object_label: str
    location_label: str | None
    lifecycle: str
    freshness: str
    aggregate_revision: int
    lots: tuple[str, ...]
    tranches: tuple[str, ...]
    projection_status: str = "CURRENT"


class ConsultationProjectionReader(Protocol):
    """Read-only, tenant-scoped query port for Consultation."""

    def get(
        self,
        *,
        tenant_id: UUID | str,
        consultation_id: UUID | str,
    ) -> ConsultationProjection | None: ...


class CaseDceReadingAvailability(StrEnum):
    """Closed availability states for one server-resolved Case reading."""

    AVAILABLE = "AVAILABLE"
    NO_APPLICABLE_DCE = "NO_APPLICABLE_DCE"
    DCE_REFERENCE_BROKEN = "DCE_REFERENCE_BROKEN"


@dataclass(frozen=True, slots=True)
class CaseDceReadingCounters:
    """Counters derived exclusively from the final closed requirement collection."""

    total: int
    pending_human_confirmation: int
    confirmed: int
    review_required: int
    not_applicable: int


@dataclass(frozen=True, slots=True)
class CaseDceReadingRequirementProjection:
    """One immutable DCE signal represented without source text or storage metadata."""

    requirement_id: UUID
    requirement_type: str
    directive_signal: str
    confirmation_outcome: str
    uncertainty_status: str
    document_family: str
    source_locator_label: str


@dataclass(frozen=True, slots=True)
class CaseDceReadingProjection:
    """Closed DCE situation applicable to one Case at one point in time."""

    dce_version_id: UUID
    lifecycle: str
    integrity: str
    classification_readiness: str
    analysis_readiness: str
    source_received_at: datetime
    requirements: tuple[CaseDceReadingRequirementProjection, ...]
    counters: CaseDceReadingCounters


@dataclass(frozen=True, slots=True)
class CaseDceReadingLookup:
    """Tenant-scoped Case lookup with an explicitly unavailable DCE state."""

    case_id: UUID
    work_label: str
    case_lifecycle: str
    commercial_stage: str
    dce_freshness: str
    availability: CaseDceReadingAvailability
    reading: CaseDceReadingProjection | None


class CaseDceReadingReader(Protocol):
    """Read-only port for the DCE applicable to one Case in one tenant."""

    def get(
        self,
        *,
        tenant_id: UUID | str,
        case_id: UUID | str,
    ) -> CaseDceReadingLookup | None: ...


@dataclass(frozen=True, slots=True)
class DceContractRiskSignalProjection:
    """Closed provenance metadata for one CCAP/CCTP contract-risk signal."""

    observation_id: UUID
    dce_version_id: UUID
    document_family: str
    requirement_kind: str
    rule_id: str
    rule_version: str
    directive: str
    fragment_id: UUID
    source_locator_label: str
    start_byte_offset: int
    end_byte_offset: int
    verification_status: str


class DceContractRiskSignalReader(Protocol):
    """Read-only tenant/case reader for detected CCAP/CCTP contract-risk signals."""

    def list_for_case(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        limit: int,
    ) -> tuple[DceContractRiskSignalProjection, ...]: ...


@dataclass(frozen=True, slots=True)
class AssignedCaseProjection:
    """Closed Case summary candidate; authorization remains a route concern."""

    case_id: UUID
    work_label: str
    case_lifecycle: str
    commercial_stage: str
    dce_availability: str


class AssignedCaseReader(Protocol):
    """Tenant-scoped candidate reader for the server-filtered Case collection."""

    def list(self, *, tenant_id: UUID | str) -> tuple[AssignedCaseProjection, ...]: ...

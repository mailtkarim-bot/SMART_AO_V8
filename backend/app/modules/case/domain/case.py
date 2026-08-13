"""Pure domain model for the AFF/Case aggregate.

This module deliberately contains no SQLAlchemy, FastAPI, Pydantic, storage or
cross-module imports. It owns only the continuity of an affair: tenant identity,
explicit scope, lifecycle and lightweight versioned references.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from .errors import (
    CaseLifecycleForbidsActionError,
    CaseScopeAmbiguousError,
    CrossTenantReferenceError,
)


class CaseLifecycle(StrEnum):
    ACTIVE = "ACTIVE"
    STOPPED = "STOPPED"
    ARCHIVED = "ARCHIVED"


class CaseStage(StrEnum):
    INTAKE = "INTAKE"
    ANALYSIS = "ANALYSIS"
    AWAITING_DECISION = "AWAITING_DECISION"
    OFFER_PREPARATION = "OFFER_PREPARATION"
    READY_FOR_PRICING = "READY_FOR_PRICING"
    PRICING = "PRICING"
    READY_FOR_FINAL_CONTROL = "READY_FOR_FINAL_CONTROL"
    READY_FOR_SUBMISSION = "READY_FOR_SUBMISSION"
    SUBMITTED = "SUBMITTED"
    OUTCOME_KNOWN = "OUTCOME_KNOWN"
    AWARDED = "AWARDED"
    EXECUTION = "EXECUTION"


class DecisionReadiness(StrEnum):
    NOT_ASSESSED = "NOT_ASSESSED"
    NOT_READY = "NOT_READY"
    READY_WITH_UNKNOWNS = "READY_WITH_UNKNOWNS"
    READY = "READY"


class DceFreshness(StrEnum):
    NO_DCE = "NO_DCE"
    CURRENT = "CURRENT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ResponsibilityStatus(StrEnum):
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    ASSIGNMENT_REVIEW_REQUIRED = "ASSIGNMENT_REVIEW_REQUIRED"


class CaseScopeKind(StrEnum):
    SINGLE_LOT = "SINGLE_LOT"
    MULTI_LOT = "MULTI_LOT"
    TRANCHE = "TRANCHE"
    VARIANT = "VARIANT"
    CUSTOM_SOURCED_SCOPE = "CUSTOM_SOURCED_SCOPE"


class CaseOriginKind(StrEnum):
    OPPORTUNITY = "OPPORTUNITY"
    MANUAL = "MANUAL"
    IMPORT = "IMPORT"
    CUSTOMER_REQUEST = "CUSTOMER_REQUEST"


@dataclass(frozen=True, slots=True)
class AggregateReference:
    """A versioned, tenant-bound reference to a foreign aggregate.

    It deliberately carries no foreign aggregate state and therefore cannot be
    used as a backdoor to mutate another bounded context.
    """

    aggregate_id: UUID
    aggregate_type: str
    tenant_id: UUID
    aggregate_revision: int

    def __post_init__(self) -> None:
        if not self.aggregate_type.strip():
            raise ValueError("aggregate type must be non-empty")
        if self.aggregate_revision < 0:
            raise ValueError("aggregate revision must be non-negative")


@dataclass(frozen=True, slots=True)
class CaseScope:
    """The explicit business perimeter of a Case.

    A Case is never created on an implicit mixture of lots, tranches or
    variants. Compatibility with a concrete Consultation is checked later by
    the application handler owning both versioned references.
    """

    kind: CaseScopeKind
    lot_numbers: tuple[str, ...] = ()
    tranche_reference: str | None = None
    variant_reference: str | None = None
    source_justification: str | None = None

    @classmethod
    def single_lot(cls, lot_number: str) -> CaseScope:
        return cls(kind=CaseScopeKind.SINGLE_LOT, lot_numbers=(lot_number,))

    @classmethod
    def multi_lot(cls, lot_numbers: tuple[str, ...], source_justification: str) -> CaseScope:
        return cls(
            kind=CaseScopeKind.MULTI_LOT,
            lot_numbers=lot_numbers,
            source_justification=source_justification,
        )

    @classmethod
    def tranche(cls, tranche_reference: str) -> CaseScope:
        return cls(kind=CaseScopeKind.TRANCHE, tranche_reference=tranche_reference)

    @classmethod
    def variant(cls, variant_reference: str) -> CaseScope:
        return cls(kind=CaseScopeKind.VARIANT, variant_reference=variant_reference)

    @classmethod
    def custom_sourced(cls, source_justification: str) -> CaseScope:
        return cls(
            kind=CaseScopeKind.CUSTOM_SOURCED_SCOPE,
            source_justification=source_justification,
        )

    def validate(self) -> None:
        lots = tuple(lot.strip() for lot in self.lot_numbers if lot.strip())
        tranche = self.tranche_reference.strip() if self.tranche_reference else ""
        variant = self.variant_reference.strip() if self.variant_reference else ""
        justification = self.source_justification.strip() if self.source_justification else ""

        if self.kind is CaseScopeKind.SINGLE_LOT:
            if len(lots) != 1 or tranche or variant or justification:
                raise CaseScopeAmbiguousError(
                    "single lot scope requires exactly one lot and no mixed scope"
                )
        elif self.kind is CaseScopeKind.MULTI_LOT:
            if len(lots) < 2:
                raise CaseScopeAmbiguousError("multi lot scope requires at least two lots")
            if not justification:
                raise CaseScopeAmbiguousError("multi lot scope requires a source justification")
            if tranche or variant:
                raise CaseScopeAmbiguousError(
                    "multi lot scope cannot mix tranche or variant references"
                )
        elif self.kind is CaseScopeKind.TRANCHE:
            if not tranche:
                raise CaseScopeAmbiguousError("tranche scope requires a tranche reference")
            if lots or variant or justification:
                raise CaseScopeAmbiguousError(
                    "tranche scope cannot mix lots, variants or justification"
                )
        elif self.kind is CaseScopeKind.VARIANT:
            if not variant:
                raise CaseScopeAmbiguousError("variant scope requires a variant reference")
            if lots or tranche or justification:
                raise CaseScopeAmbiguousError(
                    "variant scope cannot mix lots, tranche or justification"
                )
        elif self.kind is CaseScopeKind.CUSTOM_SOURCED_SCOPE:
            if not justification:
                raise CaseScopeAmbiguousError(
                    "custom sourced scope requires a source justification"
                )
            if lots or tranche or variant:
                raise CaseScopeAmbiguousError(
                    "custom sourced scope cannot mix lot, tranche or variant"
                )
        else:
            raise CaseScopeAmbiguousError("unsupported case scope kind")


@dataclass(frozen=True, slots=True)
class CaseOrigin:
    kind: CaseOriginKind
    rationale: str | None = None
    origin_reference_id: UUID | None = None

    @classmethod
    def manual(cls, rationale: str) -> CaseOrigin:
        return cls(kind=CaseOriginKind.MANUAL, rationale=rationale)

    def validate(self) -> None:
        rationale = self.rationale.strip() if self.rationale else ""
        if self.kind is CaseOriginKind.MANUAL and not rationale:
            raise CaseScopeAmbiguousError("manual case origin requires an explicit rationale")


@dataclass(frozen=True, slots=True)
class CaseCreated:
    case_id: UUID
    tenant_id: UUID


@dataclass(frozen=True, slots=True)
class CaseConsultationLinked:
    case_id: UUID
    tenant_id: UUID
    consultation_id: UUID


@dataclass(slots=True)
class Case:
    """AFF aggregate root, limited to continuity and lightweight references."""

    id: UUID
    tenant_id: UUID
    title: str
    object_description: str
    scope: CaseScope
    origin: CaseOrigin
    consultation_reference: AggregateReference | None = None
    applicable_dce_version_reference: AggregateReference | None = None
    lifecycle: CaseLifecycle = CaseLifecycle.ACTIVE
    commercial_stage: CaseStage = CaseStage.INTAKE
    decision_readiness: DecisionReadiness = DecisionReadiness.NOT_ASSESSED
    dce_freshness: DceFreshness = DceFreshness.NO_DCE
    responsibility_status: ResponsibilityStatus = ResponsibilityStatus.UNASSIGNED
    aggregate_revision: int = 0
    _pending_events: list[object] = field(default_factory=list, repr=False)

    @classmethod
    def create(
        cls,
        *,
        case_id: UUID,
        tenant_id: UUID,
        title: str,
        object_description: str,
        scope: CaseScope,
        origin: CaseOrigin,
        consultation_reference: AggregateReference | None = None,
    ) -> Case:
        if not title.strip():
            raise ValueError("case title must be non-empty")
        if not object_description.strip():
            raise ValueError("case object description must be non-empty")

        scope.validate()
        origin.validate()
        cls._validate_optional_reference_tenant(tenant_id, consultation_reference)
        if consultation_reference and consultation_reference.aggregate_type != "CONSULTATION":
            raise ValueError("case consultation reference must have aggregate type CONSULTATION")
        if origin.kind is not CaseOriginKind.MANUAL and consultation_reference is None:
            raise CaseScopeAmbiguousError(
                "non-manual case origin requires a consultation reference"
            )

        case = cls(
            id=case_id,
            tenant_id=tenant_id,
            title=title.strip(),
            object_description=object_description.strip(),
            scope=scope,
            origin=origin,
            consultation_reference=consultation_reference,
        )
        case._record(CaseCreated(case_id=case.id, tenant_id=case.tenant_id))
        return case

    @property
    def pending_events(self) -> tuple[object, ...]:
        return tuple(self._pending_events)

    def clear_pending_events(self) -> tuple[object, ...]:
        events = self.pending_events
        self._pending_events.clear()
        return events

    def register_consultation_link(self, consultation: AggregateReference) -> None:
        self._ensure_active()
        if consultation.aggregate_type != "CONSULTATION":
            raise ValueError("case consultation reference must have aggregate type CONSULTATION")
        self._validate_optional_reference_tenant(self.tenant_id, consultation)

        self.consultation_reference = consultation
        self._increment_revision()
        self._record(
            CaseConsultationLinked(
                case_id=self.id,
                tenant_id=self.tenant_id,
                consultation_id=consultation.aggregate_id,
            )
        )

    @staticmethod
    def _validate_optional_reference_tenant(
        tenant_id: UUID,
        reference: AggregateReference | None,
    ) -> None:
        if reference is not None and reference.tenant_id != tenant_id:
            raise CrossTenantReferenceError("foreign aggregate references are not permitted")

    def _ensure_active(self) -> None:
        if self.lifecycle is not CaseLifecycle.ACTIVE:
            raise CaseLifecycleForbidsActionError("case lifecycle forbids this action")

    def _increment_revision(self) -> None:
        self.aggregate_revision += 1

    def _record(self, event: object) -> None:
        self._pending_events.append(event)

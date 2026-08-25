from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DecisionDossierDecision:
    id: UUID
    aggregate_revision: int
    case_id: UUID
    decision_type: str
    lifecycle: str
    outcome: str
    validity: str
    context_status: str
    final_justification: str | None


@dataclass(frozen=True, slots=True)
class DecisionDossierContext:
    id: UUID
    canonical_context_json: Mapping[str, object]
    unknowns_json: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class DecisionDossierReference:
    aggregate_type: str
    aggregate_id: UUID
    aggregate_revision: int
    reference_role: str


@dataclass(frozen=True, slots=True)
class DecisionDossierCondition:
    id: UUID
    label: str
    status: str
    due_at: datetime | None
    failure_consequence: str


@dataclass(frozen=True, slots=True)
class DecisionDossierLookup:
    decision: DecisionDossierDecision | None
    context: DecisionDossierContext | None
    references: tuple[DecisionDossierReference, ...]
    conditions: tuple[DecisionDossierCondition, ...]


@dataclass(frozen=True, slots=True)
class DecisionRiskRequirementLinkProjection:
    link_id: UUID
    case_id: UUID
    risk_id: UUID
    requirement_id: UUID
    dce_version_id: UUID
    relationship: str
    rationale: str
    source_refs: tuple[str, ...]
    created_at: datetime
    action_id: UUID | None
    action_state: str | None
    action_severity: str | None
    action_revision: int | None


@dataclass(frozen=True, slots=True)
class DecisionRiskRequirementPage:
    items: tuple[DecisionRiskRequirementLinkProjection, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class DecisionPricingReconciliationProjection:
    link_id: UUID
    batch_id: UUID
    document_kind: str
    batch_state: str
    row_number: int
    code: str | None
    designation: str | None
    unit: str | None
    match_basis: str
    verification_status: str


class DecisionRiskRequirementReader(Protocol):
    """Reads patron-only links with a stable tenant/case cursor."""

    def list_for_case(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        limit: int,
        after_created_at: datetime | None,
        after_id: UUID | None,
    ) -> DecisionRiskRequirementPage: ...


class DecisionPricingReconciliationReader(Protocol):
    """Finds committed normalized DPGF/BPU metadata without returning prices."""

    def reconcile(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        link_id: UUID,
        search: str,
        limit: int,
    ) -> tuple[DecisionPricingReconciliationProjection, ...] | None: ...


class DecisionDossierReader(Protocol):
    """Reads one tenant-scoped patron dossier without exposing ORM records."""

    def read(self, *, tenant_id: UUID, case_id: UUID) -> DecisionDossierLookup: ...

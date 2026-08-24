"""Application port for tenant-scoped Decision persistence.

Snapshots are persistence-neutral transfer objects. A Decision handler can
rehydrate its pure aggregate without receiving mutable Case, Pricing or
Submission objects from the persistence adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.decision.domain.risk import StructuredRisk
from app.modules.decision.domain.risk_requirement import RiskRequirementLink


@dataclass(frozen=True, slots=True)
class DecisionRootSnapshot:
    id: UUID
    tenant_id: UUID
    aggregate_revision: int
    decision_type: str
    subject_type: str
    subject_id: UUID
    case_id: UUID
    scope_fingerprint: str
    decision_key_hash: str
    cycle_number: int
    lifecycle: str
    outcome: str
    validity: str
    condition_status: str
    context_status: str
    selected_final_context_id: UUID | None
    successor_decision_id: UUID | None
    final_justification: str | None
    finalized_by_actor_id: UUID | None
    finalized_at: datetime | None
    review_required_reason: str | None
    review_required_at: datetime | None
    cancel_reason: str | None
    cancelled_at: datetime | None


@dataclass(frozen=True, slots=True)
class DecisionContextSnapshot:
    id: UUID
    sequence_number: int
    context_fingerprint: str
    canonical_context_json: Mapping[str, object]
    rationale: str
    unknowns_json: tuple[object, ...]
    prepared_at: datetime
    context_state: str
    is_selected_final: bool


@dataclass(frozen=True, slots=True)
class DecisionContextReferenceSnapshot:
    id: UUID
    decision_context_id: UUID
    aggregate_type: str
    aggregate_id: UUID
    aggregate_revision: int
    content_hash: str | None
    reference_role: str


@dataclass(frozen=True, slots=True)
class DecisionConditionSnapshot:
    id: UUID
    label: str
    owner_actor_id: UUID | None
    due_at: datetime | None
    due_date_absence_reason: str | None
    failure_consequence: str
    status: str
    satisfied_evidence_ref_json: Mapping[str, object] | None
    failure_reason: str | None
    waiver_justification: str | None


@dataclass(frozen=True, slots=True)
class DecisionSnapshot:
    root: DecisionRootSnapshot
    contexts: tuple[DecisionContextSnapshot, ...]
    context_references: tuple[DecisionContextReferenceSnapshot, ...]
    conditions: tuple[DecisionConditionSnapshot, ...]


@dataclass(frozen=True, slots=True)
class DecisionRiskDraft:
    id: UUID
    tenant_id: UUID
    case_id: UUID
    dce_version_id: UUID
    source_fragment_id: UUID
    functional_key: str
    risk: StructuredRisk
    actor_id: UUID
    membership_id: UUID
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None
    due_at: datetime | None


@dataclass(frozen=True, slots=True)
class DecisionRiskRequirementLinkDraft:
    id: UUID
    tenant_id: UUID
    case_id: UUID
    risk_id: UUID
    requirement_id: UUID
    dce_version_id: UUID
    functional_key: str
    link: RiskRequirementLink
    actor_id: UUID
    membership_id: UUID
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None


class DecisionPatronActionReference(Protocol):
    id: UUID
    aggregate_revision: int


class DecisionPatronActionWriter(Protocol):
    """Creates one explainable patron action inside the caller transaction."""

    def create_from_risk_requirement_link(
        self,
        *,
        session: object,
        context: object,
        case_id: UUID,
        risk_id: UUID,
        requirement_id: UUID,
        link_id: UUID,
        command_id: UUID,
        idempotency_key: UUID,
    ) -> DecisionPatronActionReference | None: ...


class DecisionRiskRequirementLinkRepository(Protocol):
    """Persists one immutable link to a human-confirmed DCE requirement."""

    def case_exists(self, *, session: object, tenant_id: UUID, case_id: UUID) -> bool: ...

    def case_uses_dce_version(
        self, *, session: object, tenant_id: UUID, case_id: UUID, dce_version_id: UUID
    ) -> bool: ...

    def risk_matches_case_and_version(
        self,
        *,
        session: object,
        tenant_id: UUID,
        risk_id: UUID,
        case_id: UUID,
        dce_version_id: UUID,
    ) -> bool: ...

    def requirement_is_confirmed(
        self, *, session: object, tenant_id: UUID, requirement_id: UUID, dce_version_id: UUID
    ) -> bool: ...

    def functional_exists(
        self, *, session: object, tenant_id: UUID, functional_key: str
    ) -> bool: ...

    def create(self, *, session: object, draft: DecisionRiskRequirementLinkDraft) -> None: ...


class DecisionRiskRepository(Protocol):
    """Persists one immutable, tenant-scoped structured risk."""

    def case_exists(self, *, session: object, tenant_id: UUID, case_id: UUID) -> bool: ...

    def case_uses_dce_version(
        self, *, session: object, tenant_id: UUID, case_id: UUID, dce_version_id: UUID
    ) -> bool: ...

    def source_exists(
        self,
        *,
        session: object,
        tenant_id: UUID,
        dce_version_id: UUID,
        source_fragment_id: UUID,
    ) -> bool: ...

    def source_supports(
        self,
        *,
        session: object,
        tenant_id: UUID,
        dce_version_id: UUID,
        source_fragment_id: UUID,
        source_excerpt: str,
        start_byte_offset: int,
        end_byte_offset: int,
    ) -> bool: ...

    def functional_exists(
        self, *, session: object, tenant_id: UUID, functional_key: str
    ) -> bool: ...

    def create(self, *, session: object, draft: DecisionRiskDraft) -> None: ...


class DecisionVerifiedContextReader(Protocol):
    """Checks that every DCE requirement referenced by a context is confirmed."""

    def has_confirmed_dce_requirements(
        self, *, session: object, tenant_id: UUID, context_id: UUID, case_id: UUID
    ) -> bool: ...


class DecisionRepository(Protocol):
    """Persists only Decision and its owned contexts and conditions."""

    def get(
        self,
        *,
        tenant_id: UUID | str,
        aggregate_id: UUID | str,
    ) -> DecisionSnapshot | None: ...

    def update_root(
        self,
        *,
        tenant_id: UUID | str,
        aggregate_id: UUID | str,
        expected_revision: int,
        changes: Mapping[str, object],
    ) -> int: ...

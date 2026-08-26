"""Application port for tenant-scoped Decision persistence.

Snapshots are persistence-neutral transfer objects. A Decision handler can
rehydrate its pure aggregate without receiving mutable Case, Pricing or
Submission objects from the persistence adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
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
class DecisionConditionDraft:
    id: UUID
    tenant_id: UUID
    decision_id: UUID
    label: str
    owner_actor_id: UUID | None
    due_at: datetime | None
    due_date_absence_reason: str | None
    failure_consequence: str


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
class DecisionRiskSnapshot:
    id: UUID
    tenant_id: UUID
    case_id: UUID
    dce_version_id: UUID
    source_fragment_id: UUID
    risk_code: str
    category: str
    title: str
    severity: str
    likelihood: str
    treatment: str
    revision: int
    due_at: datetime | None
    latest_treatment_evidence: Mapping[str, object] | None


@dataclass(frozen=True, slots=True)
class DecisionRiskTreatmentTransitionDraft:
    id: UUID
    tenant_id: UUID
    risk_id: UUID
    from_treatment: str
    to_treatment: str
    evidence_excerpt: str
    evidence_locator: Mapping[str, object]
    evidence_start_byte_offset: int
    evidence_end_byte_offset: int
    rationale: str
    aggregate_revision: int
    actor_id: UUID
    membership_id: UUID
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None


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
    @property
    def id(self) -> UUID: ...

    @property
    def aggregate_revision(self) -> int: ...


class DecisionPatronActionWriter(Protocol):
    """Creates one explainable patron action inside the caller transaction."""

    def create_from_risk_requirement_link(
        self,
        *,
        session: Any,
        context: Any,
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

    def get_current(
        self, *, session: object, tenant_id: UUID, case_id: UUID, risk_id: UUID
    ) -> DecisionRiskSnapshot | None: ...

    def transition(
        self, *, session: object, draft: DecisionRiskTreatmentTransitionDraft
    ) -> None: ...


class DecisionVerifiedContextReader(Protocol):
    """Checks that every DCE requirement referenced by a context is confirmed."""

    def has_confirmed_dce_requirements(
        self, *, session: object, tenant_id: UUID, context_id: UUID, case_id: UUID
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class DecisionDraft:
    id: UUID
    tenant_id: UUID
    decision_type: str
    subject_type: str
    subject_id: UUID
    case_id: UUID
    scope_fingerprint: str
    decision_key_hash: str
    cycle_number: int
    actor_id: UUID


@dataclass(frozen=True, slots=True)
class DecisionContextDraft:
    id: UUID
    tenant_id: UUID
    decision_id: UUID
    sequence_number: int
    context_fingerprint: str
    canonical_context_json: Mapping[str, object]
    rationale: str
    unknowns_json: tuple[str, ...]
    prepared_at: datetime
    prepared_by_actor_id: UUID


@dataclass(frozen=True, slots=True)
class DecisionContextReferenceDraft:
    id: UUID
    tenant_id: UUID
    decision_context_id: UUID
    aggregate_type: str
    aggregate_id: UUID
    aggregate_revision: int
    content_hash: str | None
    reference_role: str


@dataclass(frozen=True, slots=True)
class DecisionConditionTransitionDraft:
    id: UUID
    tenant_id: UUID
    decision_id: UUID
    condition_id: UUID
    from_status: str
    to_status: str
    satisfied_evidence_ref_json: Mapping[str, object] | None
    failure_reason: str | None
    aggregate_revision: int
    actor_id: UUID
    membership_id: UUID
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None


class DecisionConditionRepository(Protocol):
    """Persists immutable initial conditions and append-only transitions."""

    def create_many(
        self, *, session: object, drafts: tuple[DecisionConditionDraft, ...]
    ) -> None: ...

    def transition(self, *, session: object, draft: DecisionConditionTransitionDraft) -> None: ...


class DecisionLifecycleRepository(Protocol):
    """Persists Decision roots and their immutable frozen contexts."""

    def case_exists(self, *, session: object, tenant_id: UUID, case_id: UUID) -> bool: ...

    def case_scope_fingerprint(
        self, *, session: object, tenant_id: UUID, case_id: UUID
    ) -> str | None: ...

    def active_decision_exists(
        self, *, session: object, tenant_id: UUID, decision_key_hash: str
    ) -> bool: ...

    def next_cycle_number(
        self, *, session: object, tenant_id: UUID, decision_key_hash: str
    ) -> int: ...

    def create_root(self, *, session: object, draft: DecisionDraft) -> None: ...

    def case_has_applicable_dce(
        self, *, session: object, tenant_id: UUID, case_id: UUID
    ) -> bool: ...

    def context_reference_is_valid(
        self,
        *,
        session: object,
        tenant_id: UUID,
        case_id: UUID,
        aggregate_type: str,
        aggregate_id: UUID,
        aggregate_revision: int,
        content_hash: str | None,
    ) -> bool: ...

    def create_context(
        self,
        *,
        session: object,
        context: DecisionContextDraft,
        references: tuple[DecisionContextReferenceDraft, ...],
    ) -> None: ...


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

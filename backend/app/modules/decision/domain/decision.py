"""Pure domain model for the DEC/Decision aggregate.

Decision records a human patron arbitration against a frozen context. It never
computes pricing, changes Case stage, creates tasks, or submits a response; any
such effect belongs to a correlated Process Manager in a later application layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from json import dumps
from uuid import UUID

from .errors import (
    ConditionConsequenceRequiredError,
    ConditionOwnerRequiredError,
    DecisionAlreadyFinalizedError,
    DecisionContextIncompleteError,
    DecisionLifecycleError,
    StaleDecisionContextError,
)


class DecisionType(StrEnum):
    GO_NO_GO = "GO_NO_GO"
    RISK_ACCEPTANCE = "RISK_ACCEPTANCE"
    PARTNER_SELECTION = "PARTNER_SELECTION"
    PRICING_APPROVAL = "PRICING_APPROVAL"
    SUBMISSION_AUTHORIZATION = "SUBMISSION_AUTHORIZATION"


class DecisionLifecycle(StrEnum):
    DRAFT = "DRAFT"
    PENDING_PATRON = "PENDING_PATRON"
    FINALIZED = "FINALIZED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"


class DecisionOutcome(StrEnum):
    UNDECIDED = "UNDECIDED"
    GO = "GO"
    CONDITIONAL_GO = "CONDITIONAL_GO"
    NO_GO = "NO_GO"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    AUTHORIZED = "AUTHORIZED"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"


class DecisionValidity(StrEnum):
    CURRENT = "CURRENT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


class DecisionContextStatus(StrEnum):
    INCOMPLETE = "INCOMPLETE"
    FROZEN = "FROZEN"
    STALE = "STALE"


class DecisionConditionStatus(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    OPEN = "OPEN"
    SATISFIED = "SATISFIED"
    FAILED = "FAILED"
    WAIVED = "WAIVED"


@dataclass(frozen=True, slots=True)
class DecisionContext:
    """An immutable, fingerprinted view of what the patron considered."""

    context_id: UUID
    tenant_id: UUID
    references: tuple[str, ...]
    unknowns: tuple[str, ...]
    risks: tuple[str, ...]
    prepared_at: datetime
    fingerprint: str

    @classmethod
    def build(
        cls,
        *,
        context_id: UUID,
        tenant_id: UUID,
        references: tuple[str, ...],
        unknowns: tuple[str, ...],
        risks: tuple[str, ...],
        prepared_at: datetime,
    ) -> DecisionContext:
        normalized_references = tuple(
            reference.strip() for reference in references if reference.strip()
        )
        normalized_unknowns = tuple(unknown.strip() for unknown in unknowns if unknown.strip())
        normalized_risks = tuple(risk.strip() for risk in risks if risk.strip())
        fingerprint = _context_fingerprint(
            tenant_id=tenant_id,
            references=normalized_references,
            unknowns=normalized_unknowns,
            risks=normalized_risks,
            prepared_at=prepared_at,
        )
        return cls(
            context_id=context_id,
            tenant_id=tenant_id,
            references=normalized_references,
            unknowns=normalized_unknowns,
            risks=normalized_risks,
            prepared_at=prepared_at,
            fingerprint=fingerprint,
        )


@dataclass(slots=True)
class DecisionCondition:
    """An owned condition of a conditional Go Decision."""

    id: UUID
    label: str
    owner: str | None
    due_at: datetime | None
    due_date_absence_reason: str | None
    failure_consequence: str | None
    status: DecisionConditionStatus = DecisionConditionStatus.OPEN
    evidence_reference: str | None = None
    observed_at: datetime | None = None

    @classmethod
    def proposed(
        cls,
        *,
        condition_id: UUID,
        label: str,
        owner: str | None,
        due_at: datetime | None,
        due_date_absence_reason: str | None,
        failure_consequence: str | None,
    ) -> DecisionCondition:
        return cls(
            id=condition_id,
            label=label.strip(),
            owner=owner.strip() if owner else None,
            due_at=due_at,
            due_date_absence_reason=(
                due_date_absence_reason.strip() if due_date_absence_reason else None
            ),
            failure_consequence=failure_consequence.strip() if failure_consequence else None,
        )

    def validate_for_approval(self) -> None:
        if not self.label:
            raise DecisionContextIncompleteError("decision condition requires a label")
        if not self.owner:
            raise ConditionOwnerRequiredError("conditional Go condition requires an owner")
        if self.due_at is None and not self.due_date_absence_reason:
            raise ConditionConsequenceRequiredError(
                "conditional Go condition requires a due date or absence reason"
            )
        if not self.failure_consequence:
            raise ConditionConsequenceRequiredError(
                "conditional Go condition requires a failure consequence"
            )

    def mark_satisfied(self, *, evidence_reference: str, observed_at: datetime) -> None:
        if self.status is not DecisionConditionStatus.OPEN:
            raise DecisionLifecycleError("only an open Decision condition can be satisfied")
        if not evidence_reference.strip():
            raise DecisionContextIncompleteError(
                "condition satisfaction requires evidence reference"
            )
        self.status = DecisionConditionStatus.SATISFIED
        self.evidence_reference = evidence_reference.strip()
        self.observed_at = observed_at


@dataclass(frozen=True, slots=True)
class DecisionDraftCreated:
    decision_id: UUID
    tenant_id: UUID


@dataclass(frozen=True, slots=True)
class DecisionContextPrepared:
    decision_id: UUID
    context_id: UUID
    fingerprint: str


@dataclass(frozen=True, slots=True)
class GoDecisionApproved:
    decision_id: UUID


@dataclass(frozen=True, slots=True)
class ConditionalGoDecisionApproved:
    decision_id: UUID


@dataclass(frozen=True, slots=True)
class NoGoDecisionApproved:
    decision_id: UUID


@dataclass(frozen=True, slots=True)
class DecisionConditionSatisfied:
    decision_id: UUID
    condition_id: UUID


@dataclass(frozen=True, slots=True)
class DecisionMarkedReviewRequired:
    decision_id: UUID


@dataclass(frozen=True, slots=True)
class DecisionSuperseded:
    decision_id: UUID
    successor_decision_id: UUID


@dataclass(slots=True)
class Decision:
    """DEC aggregate root with immutable final context and human outcome."""

    id: UUID
    tenant_id: UUID
    decision_type: DecisionType
    subject_reference: str
    scope_fingerprint: str
    created_by: str
    lifecycle: DecisionLifecycle = DecisionLifecycle.DRAFT
    outcome: DecisionOutcome = DecisionOutcome.UNDECIDED
    validity: DecisionValidity = DecisionValidity.CURRENT
    context_status: DecisionContextStatus = DecisionContextStatus.INCOMPLETE
    condition_status: DecisionConditionStatus = DecisionConditionStatus.NOT_APPLICABLE
    context_history: list[DecisionContext] = field(default_factory=list)
    conditions: list[DecisionCondition] = field(default_factory=list)
    successor_decision_id: UUID | None = None
    final_justification: str | None = None
    final_approved_by: str | None = None
    final_approved_at: datetime | None = None
    aggregate_revision: int = 0
    _pending_events: list[object] = field(default_factory=list, repr=False)

    @classmethod
    def create_draft(
        cls,
        *,
        decision_id: UUID,
        tenant_id: UUID,
        decision_type: DecisionType,
        subject_reference: str,
        scope_fingerprint: str,
        created_by: str,
    ) -> Decision:
        if not subject_reference.strip() or not scope_fingerprint.strip() or not created_by.strip():
            raise DecisionContextIncompleteError(
                "Decision draft requires subject, scope fingerprint and creator"
            )
        decision = cls(
            id=decision_id,
            tenant_id=tenant_id,
            decision_type=decision_type,
            subject_reference=subject_reference.strip(),
            scope_fingerprint=scope_fingerprint.strip(),
            created_by=created_by.strip(),
        )
        decision._record(
            DecisionDraftCreated(
                decision_id=decision.id,
                tenant_id=decision.tenant_id,
            )
        )
        return decision

    @property
    def current_context(self) -> DecisionContext:
        if not self.context_history:
            raise DecisionContextIncompleteError("Decision has no prepared context")
        return self.context_history[-1]

    @property
    def pending_events(self) -> tuple[object, ...]:
        return tuple(self._pending_events)

    def prepare_context(self, context: DecisionContext) -> None:
        self._ensure_not_finalized()
        if context.tenant_id != self.tenant_id:
            raise DecisionContextIncompleteError("Decision context belongs to another tenant")
        if not context.references:
            raise DecisionContextIncompleteError("Decision context requires references")
        self.context_history.append(context)
        self.lifecycle = DecisionLifecycle.PENDING_PATRON
        self.context_status = DecisionContextStatus.FROZEN
        self._increment_revision()
        self._record(
            DecisionContextPrepared(
                decision_id=self.id,
                context_id=context.context_id,
                fingerprint=context.fingerprint,
            )
        )

    def approve_go(
        self,
        *,
        displayed_fingerprint: str,
        justification: str,
        approved_by: str,
        approved_at: datetime,
    ) -> None:
        self._ensure_pending_current_context(displayed_fingerprint)
        self._finalize(
            outcome=DecisionOutcome.GO,
            justification=justification,
            approved_by=approved_by,
            approved_at=approved_at,
        )
        self.condition_status = DecisionConditionStatus.NOT_APPLICABLE
        self._record(GoDecisionApproved(decision_id=self.id))

    def approve_conditional_go(
        self,
        *,
        displayed_fingerprint: str,
        justification: str,
        conditions: tuple[DecisionCondition, ...],
        approved_by: str,
        approved_at: datetime,
    ) -> None:
        self._ensure_pending_current_context(displayed_fingerprint)
        if not conditions:
            raise DecisionContextIncompleteError("conditional Go requires at least one condition")
        if len({condition.id for condition in conditions}) != len(conditions):
            raise DecisionContextIncompleteError(
                "conditional Go condition identifiers must be unique"
            )
        for condition in conditions:
            condition.validate_for_approval()
        self.conditions = list(conditions)
        self._finalize(
            outcome=DecisionOutcome.CONDITIONAL_GO,
            justification=justification,
            approved_by=approved_by,
            approved_at=approved_at,
        )
        self.condition_status = DecisionConditionStatus.OPEN
        self._record(ConditionalGoDecisionApproved(decision_id=self.id))

    def approve_no_go(
        self,
        *,
        displayed_fingerprint: str,
        justification: str,
        approved_by: str,
        approved_at: datetime,
    ) -> None:
        self._ensure_pending_current_context(displayed_fingerprint)
        self._finalize(
            outcome=DecisionOutcome.NO_GO,
            justification=justification,
            approved_by=approved_by,
            approved_at=approved_at,
        )
        self.condition_status = DecisionConditionStatus.NOT_APPLICABLE
        self._record(NoGoDecisionApproved(decision_id=self.id))

    def record_condition_satisfied(
        self,
        *,
        condition_id: UUID,
        evidence_reference: str,
        observed_at: datetime,
    ) -> None:
        if self.lifecycle is not DecisionLifecycle.FINALIZED:
            raise DecisionLifecycleError("only a finalized conditional Decision has conditions")
        if self.outcome is not DecisionOutcome.CONDITIONAL_GO:
            raise DecisionLifecycleError("Decision outcome does not support conditions")
        condition = self._find_open_condition(condition_id)
        condition.mark_satisfied(evidence_reference=evidence_reference, observed_at=observed_at)
        self.condition_status = self._derive_condition_status()
        self._increment_revision()
        self._record(DecisionConditionSatisfied(decision_id=self.id, condition_id=condition.id))

    def mark_review_required(self, *, reason: str) -> None:
        if self.lifecycle is not DecisionLifecycle.FINALIZED:
            raise DecisionLifecycleError("only a finalized Decision can require review")
        if not reason.strip():
            raise DecisionContextIncompleteError("review required needs an impact reason")
        self.validity = DecisionValidity.REVIEW_REQUIRED
        self.context_status = DecisionContextStatus.STALE
        self._increment_revision()
        self._record(DecisionMarkedReviewRequired(decision_id=self.id))

    def supersede(self, *, successor_decision_id: UUID, rationale: str) -> None:
        if self.lifecycle is not DecisionLifecycle.FINALIZED:
            raise DecisionLifecycleError("only a finalized Decision can be superseded")
        if successor_decision_id == self.id or not rationale.strip():
            raise DecisionContextIncompleteError(
                "Decision supersession requires another Decision and rationale"
            )
        self.lifecycle = DecisionLifecycle.SUPERSEDED
        self.validity = DecisionValidity.SUPERSEDED
        self.successor_decision_id = successor_decision_id
        self._increment_revision()
        self._record(
            DecisionSuperseded(
                decision_id=self.id,
                successor_decision_id=successor_decision_id,
            )
        )

    def _ensure_not_finalized(self) -> None:
        if self.lifecycle is DecisionLifecycle.FINALIZED:
            raise DecisionAlreadyFinalizedError("finalized Decision cannot be modified")
        if self.lifecycle in {DecisionLifecycle.SUPERSEDED, DecisionLifecycle.CANCELLED}:
            raise DecisionLifecycleError("Decision lifecycle forbids this action")

    def _ensure_pending_current_context(self, displayed_fingerprint: str) -> None:
        if self.lifecycle is DecisionLifecycle.FINALIZED:
            raise DecisionAlreadyFinalizedError("finalized Decision cannot be approved again")
        if self.lifecycle is not DecisionLifecycle.PENDING_PATRON:
            raise DecisionLifecycleError("Decision requires a frozen pending context")
        if displayed_fingerprint != self.current_context.fingerprint:
            raise StaleDecisionContextError("displayed Decision context fingerprint is stale")

    def _finalize(
        self,
        *,
        outcome: DecisionOutcome,
        justification: str,
        approved_by: str,
        approved_at: datetime,
    ) -> None:
        if not justification.strip() or not approved_by.strip():
            raise DecisionContextIncompleteError(
                "Decision finalization requires justification and patron"
            )
        self.lifecycle = DecisionLifecycle.FINALIZED
        self.outcome = outcome
        self.validity = DecisionValidity.CURRENT
        self.final_justification = justification.strip()
        self.final_approved_by = approved_by.strip()
        self.final_approved_at = approved_at
        self._increment_revision()

    def _find_open_condition(self, condition_id: UUID) -> DecisionCondition:
        for condition in self.conditions:
            if condition.id == condition_id:
                if condition.status is not DecisionConditionStatus.OPEN:
                    raise DecisionLifecycleError("Decision condition is not open")
                return condition
        raise DecisionLifecycleError("Decision condition is not found")

    def _derive_condition_status(self) -> DecisionConditionStatus:
        if any(condition.status is DecisionConditionStatus.FAILED for condition in self.conditions):
            return DecisionConditionStatus.FAILED
        if all(
            condition.status in {DecisionConditionStatus.SATISFIED, DecisionConditionStatus.WAIVED}
            for condition in self.conditions
        ):
            return DecisionConditionStatus.SATISFIED
        return DecisionConditionStatus.OPEN

    def _increment_revision(self) -> None:
        self.aggregate_revision += 1

    def _record(self, event: object) -> None:
        self._pending_events.append(event)


def _context_fingerprint(
    *,
    tenant_id: UUID,
    references: tuple[str, ...],
    unknowns: tuple[str, ...],
    risks: tuple[str, ...],
    prepared_at: datetime,
) -> str:
    payload = {
        "tenant_id": str(tenant_id),
        "references": references,
        "unknowns": unknowns,
        "risks": risks,
        "prepared_at": prepared_at.isoformat(),
    }
    canonical = dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(canonical.encode("utf-8")).hexdigest()

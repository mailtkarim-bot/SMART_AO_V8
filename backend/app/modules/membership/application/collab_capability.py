from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.dce.infrastructure.models.dce_requirements import DceRequirementRecord
from app.modules.enterprise.infrastructure.models import (
    CaseCapabilityGapRecord,
    CaseCapabilityProposalRecord,
    EnterpriseCapabilityRecord,
    EnterpriseCapabilityVersionRecord,
)
from app.modules.membership.application.collab_capability_commands import (
    ProposeCapabilityForCaseCommand,
    ReportCapabilityGapCommand,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
    DispatchResult,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification
from app.platform.security.models import (
    CaseAssignmentRecord,
    CollaboratorTaskRecord,
)


@dataclass(frozen=True, slots=True)
class CapabilityProposalProjection:
    proposal_id: UUID
    case_id: UUID
    assignment_id: UUID
    capability_id: UUID
    capability_version_id: UUID
    requirement_id: UUID | None
    task_id: UUID | None
    state: str
    validity_state: str
    justification: str
    source_locator: str | None


@dataclass(frozen=True, slots=True)
class CapabilityGapProjection:
    gap_id: UUID
    case_id: UUID
    assignment_id: UUID
    capability_id: UUID | None
    requirement_id: UUID | None
    task_id: UUID | None
    gap_kind: str
    severity: str
    reason: str
    source_locator: str | None
    recommended_action: str


@dataclass(frozen=True, slots=True)
class CollaboratorCapabilityAssessmentProjection:
    proposals: tuple[CapabilityProposalProjection, ...]
    gaps: tuple[CapabilityGapProjection, ...]


def _require_active_assignment(
    session: Session,
    *,
    context: CommandContext,
    case_id: UUID,
    assignment_id: UUID,
    required_action: Capability,
) -> CaseAssignmentRecord:
    if context.membership_id is None:
        raise CommandExecutionError("ASSIGNMENT_REQUIRED")
    assignment = session.scalar(
        sa.select(CaseAssignmentRecord).where(
            CaseAssignmentRecord.tenant_id == context.tenant_id,
            CaseAssignmentRecord.id == assignment_id,
            CaseAssignmentRecord.case_id == case_id,
            CaseAssignmentRecord.membership_id == context.membership_id,
            CaseAssignmentRecord.state == "ACTIVE",
            CaseAssignmentRecord.starts_at <= context.received_at,
            sa.or_(
                CaseAssignmentRecord.ends_at.is_(None),
                CaseAssignmentRecord.ends_at > context.received_at,
            ),
        )
    )
    if assignment is None:
        raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
    if required_action.value not in assignment.scope_actions_json:
        raise CommandExecutionError("SCOPE_DENIED")
    return assignment


def _validate_source(
    session: Session,
    *,
    tenant_id: UUID,
    case_id: UUID,
    assignment_id: UUID,
    requirement_id: UUID | None,
    task_id: UUID | None,
) -> None:
    if requirement_id is None and task_id is None:
        raise CommandExecutionError("CAPABILITY_SOURCE_REQUIRED")
    if requirement_id is not None:
        requirement = session.scalar(
            sa.select(DceRequirementRecord).where(
                DceRequirementRecord.tenant_id == tenant_id,
                DceRequirementRecord.id == requirement_id,
            )
        )
        if requirement is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
    if task_id is not None:
        task = session.scalar(
            sa.select(CollaboratorTaskRecord).where(
                CollaboratorTaskRecord.tenant_id == tenant_id,
                CollaboratorTaskRecord.id == task_id,
                CollaboratorTaskRecord.case_id == case_id,
                CollaboratorTaskRecord.assignment_id == assignment_id,
            )
        )
        if task is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")


class CollaboratorCapabilityAssessmentService:
    """Case-scoped evidence proposals and gaps; never mutates the enterprise catalog."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._policy = policy

    def propose_capability(
        self,
        *,
        actor: ActorContext,
        command: ProposeCapabilityForCaseCommand,
        now: datetime,
    ) -> DispatchResult:
        self._authorize(
            actor=actor,
            case_id=command.case_id,
            now=now,
            action=Capability.PREPARATION_CAPABILITY_PROPOSE,
        )
        self._preflight_assignment(
            actor=actor, command=command, now=now, action=Capability.PREPARATION_CAPABILITY_PROPOSE
        )
        return self._dispatcher.dispatch(
            command=command, context=self._context(actor=actor, now=now, case_id=command.case_id)
        )

    def report_gap(
        self,
        *,
        actor: ActorContext,
        command: ReportCapabilityGapCommand,
        now: datetime,
    ) -> DispatchResult:
        self._authorize(
            actor=actor,
            case_id=command.case_id,
            now=now,
            action=Capability.PREPARATION_CAPABILITY_GAP_REPORT,
        )
        self._preflight_assignment(
            actor=actor,
            command=command,
            now=now,
            action=Capability.PREPARATION_CAPABILITY_GAP_REPORT,
        )
        return self._dispatcher.dispatch(
            command=command, context=self._context(actor=actor, now=now, case_id=command.case_id)
        )

    def read_assessments(
        self,
        *,
        actor: ActorContext,
        case_id: UUID,
        assignment_id: UUID,
        now: datetime,
    ) -> CollaboratorCapabilityAssessmentProjection:
        self._authorize(
            actor=actor, case_id=case_id, now=now, action=Capability.PREPARATION_CAPABILITY_PROPOSE
        )
        with self._session_factory() as session:
            _require_active_assignment(
                session,
                context=self._context(actor=actor, now=now, case_id=case_id),
                case_id=case_id,
                assignment_id=assignment_id,
                required_action=Capability.PREPARATION_CAPABILITY_PROPOSE,
            )
            proposals = list(
                session.scalars(
                    sa.select(CaseCapabilityProposalRecord)
                    .where(
                        CaseCapabilityProposalRecord.tenant_id == actor.tenant_id,
                        CaseCapabilityProposalRecord.case_id == case_id,
                        CaseCapabilityProposalRecord.assignment_id == assignment_id,
                    )
                    .order_by(
                        CaseCapabilityProposalRecord.created_at, CaseCapabilityProposalRecord.id
                    )
                )
            )
            gaps = list(
                session.scalars(
                    sa.select(CaseCapabilityGapRecord)
                    .where(
                        CaseCapabilityGapRecord.tenant_id == actor.tenant_id,
                        CaseCapabilityGapRecord.case_id == case_id,
                        CaseCapabilityGapRecord.assignment_id == assignment_id,
                    )
                    .order_by(CaseCapabilityGapRecord.created_at, CaseCapabilityGapRecord.id)
                )
            )
        return CollaboratorCapabilityAssessmentProjection(
            proposals=tuple(
                CapabilityProposalProjection(
                    proposal_id=item.id,
                    case_id=item.case_id,
                    assignment_id=item.assignment_id,
                    capability_id=item.capability_id,
                    capability_version_id=item.capability_version_id,
                    requirement_id=item.requirement_id,
                    task_id=item.task_id,
                    state=item.state,
                    validity_state=item.validity_state,
                    justification=item.justification,
                    source_locator=item.source_locator,
                )
                for item in proposals
            ),
            gaps=tuple(
                CapabilityGapProjection(
                    gap_id=item.id,
                    case_id=item.case_id,
                    assignment_id=item.assignment_id,
                    capability_id=item.capability_id,
                    requirement_id=item.requirement_id,
                    task_id=item.task_id,
                    gap_kind=item.gap_kind,
                    severity=item.severity,
                    reason=item.reason,
                    source_locator=item.source_locator,
                    recommended_action=item.recommended_action,
                )
                for item in gaps
            ),
        )

    def _preflight_assignment(
        self, *, actor: ActorContext, command, now: datetime, action: Capability
    ) -> None:
        with self._session_factory() as session:
            context = self._context(actor=actor, now=now, case_id=command.case_id)
            _require_active_assignment(
                session,
                context=context,
                case_id=command.case_id,
                assignment_id=command.assignment_id,
                required_action=action,
            )

    def _authorize(
        self, *, actor: ActorContext, case_id: UUID, now: datetime, action: Capability
    ) -> None:
        if actor.actor_kind is not ActorKind.COLLABORATEUR or actor.membership_id is None:
            raise PermissionError("COLLABORATOR_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=action,
                resource=AuthorizationResource(
                    resource_type="CASE_CAPABILITY",
                    resource_id=case_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)

    @staticmethod
    def _context(*, actor: ActorContext, now: datetime, case_id: UUID) -> CommandContext:
        return CommandContext(
            tenant_id=actor.tenant_id,
            actor_id=actor.actor_id,
            actor_kind=actor.actor_kind.value,
            received_at=now,
            identity_id=actor.identity_id,
            membership_id=actor.membership_id,
            session_id=actor.session_id,
            case_id=case_id,
            correlation_id=actor.correlation_id,
        )


class ProposeCapabilityForCaseHandler:
    def execute(
        self,
        *,
        session: Session,
        command: ProposeCapabilityForCaseCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        _require_active_assignment(
            session,
            context=context,
            case_id=command.case_id,
            assignment_id=command.assignment_id,
            required_action=Capability.PREPARATION_CAPABILITY_PROPOSE,
        )
        _validate_source(
            session,
            tenant_id=context.tenant_id,
            case_id=command.case_id,
            assignment_id=command.assignment_id,
            requirement_id=command.requirement_id,
            task_id=command.task_id,
        )
        version = session.scalar(
            sa.select(EnterpriseCapabilityVersionRecord).where(
                EnterpriseCapabilityVersionRecord.tenant_id == context.tenant_id,
                EnterpriseCapabilityVersionRecord.id == command.capability_version_id,
                EnterpriseCapabilityVersionRecord.capability_id == command.capability_id,
            )
        )
        capability = session.scalar(
            sa.select(EnterpriseCapabilityRecord).where(
                EnterpriseCapabilityRecord.tenant_id == context.tenant_id,
                EnterpriseCapabilityRecord.id == command.capability_id,
            )
        )
        if version is None or capability is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        validity_state = (
            "CURRENT"
            if capability.state == "ACTIVE"
            and version.valid_from <= context.received_at
            and (version.valid_until is None or version.valid_until > context.received_at)
            else "EXPIRED"
        )
        functional_key = ":".join(
            [
                str(command.case_id),
                str(command.capability_version_id),
                str(command.requirement_id or ""),
                str(command.task_id or ""),
            ]
        )
        existing = session.scalar(
            sa.select(CaseCapabilityProposalRecord).where(
                CaseCapabilityProposalRecord.tenant_id == context.tenant_id,
                CaseCapabilityProposalRecord.functional_key == functional_key,
            )
        )
        if existing is not None:
            raise CommandExecutionError("CAPABILITY_PROPOSAL_ALREADY_EXISTS")
        session.add(
            CaseCapabilityProposalRecord(
                id=command.proposal_id,
                tenant_id=context.tenant_id,
                case_id=command.case_id,
                assignment_id=command.assignment_id,
                capability_id=command.capability_id,
                capability_version_id=command.capability_version_id,
                requirement_id=command.requirement_id,
                task_id=command.task_id,
                state="PROPOSED",
                validity_state=validity_state,
                justification=command.justification,
                source_locator=command.source_locator,
                functional_key=functional_key,
                proposed_by_membership_id=context.membership_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )
        return HandlerOutcome(
            result_code="CAPABILITY_PROPOSED_FOR_CASE",
            aggregate_refs=(
                {
                    "aggregate_type": "CaseCapabilityProposal",
                    "aggregate_id": str(command.proposal_id),
                    "aggregate_revision": 0,
                    "validity_state": validity_state,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="CaseCapabilityProposal",
                    aggregate_id=command.proposal_id,
                    aggregate_revision=0,
                    event_type="CapabilityProposedForCase",
                    payload={
                        "proposal_id": str(command.proposal_id),
                        "case_id": str(command.case_id),
                        "capability_id": str(command.capability_id),
                        "capability_version_id": str(command.capability_version_id),
                        "validity_state": validity_state,
                    },
                ),
            ),
        )


class ReportCapabilityGapHandler:
    def execute(
        self,
        *,
        session: Session,
        command: ReportCapabilityGapCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        _require_active_assignment(
            session,
            context=context,
            case_id=command.case_id,
            assignment_id=command.assignment_id,
            required_action=Capability.PREPARATION_CAPABILITY_GAP_REPORT,
        )
        _validate_source(
            session,
            tenant_id=context.tenant_id,
            case_id=command.case_id,
            assignment_id=command.assignment_id,
            requirement_id=command.requirement_id,
            task_id=command.task_id,
        )
        if command.capability_id is not None:
            capability_exists = session.scalar(
                sa.select(EnterpriseCapabilityRecord.id).where(
                    EnterpriseCapabilityRecord.tenant_id == context.tenant_id,
                    EnterpriseCapabilityRecord.id == command.capability_id,
                )
            )
            if capability_exists is None:
                raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        functional_key = ":".join(
            [
                str(command.case_id),
                str(command.capability_id or ""),
                str(command.requirement_id or ""),
                str(command.task_id or ""),
                command.gap_kind,
            ]
        )
        existing = session.scalar(
            sa.select(CaseCapabilityGapRecord).where(
                CaseCapabilityGapRecord.tenant_id == context.tenant_id,
                CaseCapabilityGapRecord.functional_key == functional_key,
            )
        )
        if existing is not None:
            raise CommandExecutionError("CAPABILITY_GAP_ALREADY_REPORTED")
        session.add(
            CaseCapabilityGapRecord(
                id=command.gap_id,
                tenant_id=context.tenant_id,
                case_id=command.case_id,
                assignment_id=command.assignment_id,
                capability_id=command.capability_id,
                requirement_id=command.requirement_id,
                task_id=command.task_id,
                gap_kind=command.gap_kind,
                severity=command.severity,
                reason=command.reason,
                source_locator=command.source_locator,
                recommended_action=command.recommended_action,
                functional_key=functional_key,
                reported_by_membership_id=context.membership_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )
        return HandlerOutcome(
            result_code="CAPABILITY_GAP_REPORTED",
            aggregate_refs=(
                {
                    "aggregate_type": "CaseCapabilityGap",
                    "aggregate_id": str(command.gap_id),
                    "aggregate_revision": 0,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="CaseCapabilityGap",
                    aggregate_id=command.gap_id,
                    aggregate_revision=0,
                    event_type="CapabilityGapReported",
                    payload={
                        "gap_id": str(command.gap_id),
                        "case_id": str(command.case_id),
                        "capability_id": str(command.capability_id)
                        if command.capability_id
                        else None,
                        "gap_kind": command.gap_kind,
                        "severity": command.severity,
                    },
                ),
            ),
        )


def collaborator_capability_handlers() -> dict[str, object]:
    return {
        "ProposeCapabilityForCase": ProposeCapabilityForCaseHandler(),
        "ReportCapabilityGap": ReportCapabilityGapHandler(),
    }

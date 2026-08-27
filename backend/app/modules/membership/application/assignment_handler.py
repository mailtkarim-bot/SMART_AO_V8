"""Transactional handlers for collaborator assignment interactions."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.membership.infrastructure.records import (
    AssignmentClarificationRequestRecord,
    CaseAssignmentAcknowledgementRecord,
    CaseAssignmentRecord,
    CaseAssignmentUnavailabilityRecord,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandExecutionError,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorKind, DataClassification

_ACTION_BY_COMMAND = {
    "AcknowledgeAssignment": Capability.ASSIGNMENT_ACKNOWLEDGE,
    "RequestAssignmentClarification": Capability.ASSIGNMENT_CLARIFY,
    "ReportAssignmentUnavailability": Capability.ASSIGNMENT_UNAVAILABILITY,
}


class AssignmentInteractionHandler:
    """Own all three Assignment interaction mutations behind one dispatcher adapter."""

    def execute(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        if context.actor_kind != ActorKind.COLLABORATEUR.value:
            raise CommandExecutionError("ASSIGNMENT_COLLABORATOR_REQUIRED")
        if context.membership_id is None:
            raise CommandExecutionError("ASSIGNMENT_MEMBERSHIP_CONTEXT_REQUIRED")

        assignment = session.scalar(
            sa.select(CaseAssignmentRecord)
            .where(
                CaseAssignmentRecord.tenant_id == context.tenant_id,
                CaseAssignmentRecord.id == command.assignment_id,
            )
            .with_for_update()
        )
        if assignment is None or assignment.membership_id != context.membership_id:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if assignment.state != "ACTIVE":
            raise CommandExecutionError("ASSIGNMENT_INACTIVE")
        if assignment.starts_at > context.received_at or (
            assignment.ends_at is not None and assignment.ends_at <= context.received_at
        ):
            raise CommandExecutionError("ASSIGNMENT_INACTIVE")
        if assignment.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("VERSION_CONFLICT")

        case = session.scalar(
            sa.select(CaseRecord).where(
                CaseRecord.tenant_id == context.tenant_id,
                CaseRecord.id == assignment.case_id,
            )
        )
        if case is None or case.lifecycle == "ARCHIVED":
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if context.case_id is not None and context.case_id != assignment.case_id:
            raise CommandExecutionError("CASE_CONTEXT_MISMATCH")

        required_action = _ACTION_BY_COMMAND[command.command_type]
        if required_action not in assignment.scope_actions_json:
            raise CommandExecutionError("ASSIGNMENT_SCOPE_FORBIDDEN")
        if (
            DataClassification.INTERNAL_OPERATIONAL.value
            not in assignment.scope_classifications_json
        ):
            raise CommandExecutionError("ASSIGNMENT_CLASSIFICATION_FORBIDDEN")

        if command.command_type == "AcknowledgeAssignment":
            return self._acknowledge(
                session=session,
                assignment=assignment,
                command=command,
                context=context,
            )
        if command.command_type == "RequestAssignmentClarification":
            return self._clarify(
                session=session,
                assignment=assignment,
                command=command,
                context=context,
            )
        if command.command_type == "ReportAssignmentUnavailability":
            return self._unavailability(
                session=session,
                assignment=assignment,
                command=command,
                context=context,
            )
        raise CommandExecutionError(f"unsupported assignment command: {command.command_type}")

    @staticmethod
    def _acknowledge(*, session, assignment, command, context) -> HandlerOutcome:
        revision = assignment.aggregate_revision + 1
        acknowledgement = CaseAssignmentAcknowledgementRecord(
            id=uuid4(),
            tenant_id=context.tenant_id,
            assignment_id=assignment.id,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            assignment_revision=revision,
            note=command.note,
            command_id=command.command_id,
            correlation_id=command.correlation_id,
        )
        assignment.aggregate_revision = revision
        session.add(acknowledgement)
        return HandlerOutcome(
            result_code="ASSIGNMENT_ACKNOWLEDGED",
            aggregate_refs=(
                {
                    "aggregate_type": "Assignment",
                    "aggregate_id": str(assignment.id),
                    "aggregate_revision": revision,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="Assignment",
                    aggregate_id=assignment.id,
                    aggregate_revision=revision,
                    event_type="AssignmentAcknowledged",
                    payload={
                        "assignment_id": str(assignment.id),
                        "case_id": str(assignment.case_id),
                        "membership_id": str(context.membership_id),
                        "assignment_revision": revision,
                    },
                ),
            ),
        )

    @staticmethod
    def _clarify(*, session, assignment, command, context) -> HandlerOutcome:
        functional_key = _clarification_functional_key(
            assignment_id=assignment.id,
            case_id=assignment.case_id,
            command=command,
        )
        existing = session.scalar(
            sa.select(AssignmentClarificationRequestRecord).where(
                AssignmentClarificationRequestRecord.tenant_id == context.tenant_id,
                AssignmentClarificationRequestRecord.functional_key == functional_key,
            )
        )
        if existing is not None:
            return HandlerOutcome(
                result_code="ASSIGNMENT_CLARIFICATION_REQUESTED",
                aggregate_refs=(
                    {
                        "aggregate_type": "AssignmentClarificationRequest",
                        "aggregate_id": str(existing.id),
                        "aggregate_revision": 1,
                    },
                ),
                events=(),
            )

        request = AssignmentClarificationRequestRecord(
            id=uuid4(),
            tenant_id=context.tenant_id,
            assignment_id=assignment.id,
            case_id=assignment.case_id,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            clarification_kind=command.clarification_kind,
            subject=command.subject,
            question=command.question,
            requested_scope=command.requested_scope,
            priority=command.priority,
            state="OPEN",
            functional_key=functional_key,
            command_id=command.command_id,
            correlation_id=command.correlation_id,
        )
        session.add(request)
        return HandlerOutcome(
            result_code="ASSIGNMENT_CLARIFICATION_REQUESTED",
            aggregate_refs=(
                {
                    "aggregate_type": "AssignmentClarificationRequest",
                    "aggregate_id": str(request.id),
                    "aggregate_revision": 1,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="AssignmentClarificationRequest",
                    aggregate_id=request.id,
                    aggregate_revision=1,
                    event_type="AssignmentClarificationRequested",
                    payload={
                        "request_id": str(request.id),
                        "assignment_id": str(assignment.id),
                        "case_id": str(assignment.case_id),
                        "clarification_kind": command.clarification_kind,
                        "priority": command.priority,
                        "state": "OPEN",
                    },
                ),
            ),
        )

    @staticmethod
    def _unavailability(*, session, assignment, command, context) -> HandlerOutcome:
        revision = assignment.aggregate_revision + 1
        unavailability = CaseAssignmentUnavailabilityRecord(
            id=uuid4(),
            tenant_id=context.tenant_id,
            assignment_id=assignment.id,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            assignment_revision=revision,
            reason_kind=command.reason_kind,
            reason=command.reason,
            unavailable_from=command.unavailable_from,
            unavailable_until=command.unavailable_until,
            known_deadline_impact=command.known_deadline_impact,
            impact_note=command.impact_note,
            command_id=command.command_id,
            correlation_id=command.correlation_id,
        )
        assignment.aggregate_revision = revision
        session.add(unavailability)
        return HandlerOutcome(
            result_code="ASSIGNMENT_UNAVAILABILITY_REPORTED",
            aggregate_refs=(
                {
                    "aggregate_type": "Assignment",
                    "aggregate_id": str(assignment.id),
                    "aggregate_revision": revision,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="Assignment",
                    aggregate_id=assignment.id,
                    aggregate_revision=revision,
                    event_type="AssignmentUnavailabilityReported",
                    payload={
                        "assignment_id": str(assignment.id),
                        "case_id": str(assignment.case_id),
                        "membership_id": str(context.membership_id),
                        "assignment_revision": revision,
                        "reason_kind": command.reason_kind,
                        "known_deadline_impact": command.known_deadline_impact,
                    },
                ),
            ),
        )


def _clarification_functional_key(*, assignment_id: UUID, case_id: UUID, command) -> str:
    payload = {
        "assignment_id": str(assignment_id),
        "case_id": str(case_id),
        "clarification_kind": command.clarification_kind,
        "subject": command.subject,
        "question": command.question,
        "requested_scope": command.requested_scope,
        "priority": command.priority,
    }
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def assignment_handlers() -> dict[str, AssignmentInteractionHandler]:
    """Return the closed command registrations for the membership slice."""

    handler = AssignmentInteractionHandler()
    return {
        "AcknowledgeAssignment": handler,
        "RequestAssignmentClarification": handler,
        "ReportAssignmentUnavailability": handler,
    }

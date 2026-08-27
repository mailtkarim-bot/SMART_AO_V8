"""COLLAB-ASSIGNMENT-01 command façade."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.dce.application.commands import (
    AcknowledgeAssignmentCommand,
    ReportAssignmentUnavailabilityCommand,
    RequestAssignmentClarificationCommand,
)
from app.modules.membership.application.assignment_handler import (
    AssignmentInteractionHandler,
    assignment_handlers,
)
from app.modules.membership.application.queries import (
    AssignmentManagementReader,
    AssignmentManagementTarget,
)
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, DispatchResult
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification

_ACTION_BY_COMMAND = {
    "AcknowledgeAssignment": Capability.ASSIGNMENT_ACKNOWLEDGE,
    "RequestAssignmentClarification": Capability.ASSIGNMENT_CLARIFY,
    "ReportAssignmentUnavailability": Capability.ASSIGNMENT_UNAVAILABILITY,
}


class AssignmentInteractionService:
    """Resolve server-owned assignment scope, authorize, then dispatch one command."""

    def __init__(
        self,
        *,
        reader: AssignmentManagementReader,
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._reader = reader
        self._dispatcher = dispatcher
        self._policy = policy

    def acknowledge(
        self,
        *,
        actor: ActorContext,
        command: AcknowledgeAssignmentCommand,
        now: datetime,
    ) -> DispatchResult:
        return self._authorize_and_dispatch(actor=actor, command=command, now=now)

    def clarify(
        self,
        *,
        actor: ActorContext,
        command: RequestAssignmentClarificationCommand,
        now: datetime,
    ) -> DispatchResult:
        return self._authorize_and_dispatch(actor=actor, command=command, now=now)

    def report_unavailability(
        self,
        *,
        actor: ActorContext,
        command: ReportAssignmentUnavailabilityCommand,
        now: datetime,
    ) -> DispatchResult:
        return self._authorize_and_dispatch(actor=actor, command=command, now=now)

    def _authorize_and_dispatch(self, *, actor: ActorContext, command, now: datetime):
        if actor.actor_kind is not ActorKind.COLLABORATEUR:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="ASSIGNMENT_COLLABORATOR_REQUIRED",
            )
            raise PermissionError("ASSIGNMENT_COLLABORATOR_REQUIRED")
        if actor.membership_id is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="ASSIGNMENT_MEMBERSHIP_REQUIRED",
            )
            raise PermissionError("ASSIGNMENT_MEMBERSHIP_REQUIRED")

        assignment = self._resolve_assignment(
            tenant_id=actor.tenant_id,
            membership_id=actor.membership_id,
            assignment_id=command.assignment_id,
        )
        if assignment is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        action = _ACTION_BY_COMMAND[command.command_type]
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=action,
                resource=AuthorizationResource(
                    resource_type="CASE_ASSIGNMENT",
                    resource_id=assignment.id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=assignment.case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)

        return self._dispatcher.dispatch(
            command=command,
            context=CommandContext(
                tenant_id=actor.tenant_id,
                actor_id=actor.actor_id,
                actor_kind=actor.actor_kind.value,
                received_at=now,
                identity_id=actor.identity_id,
                membership_id=actor.membership_id,
                session_id=actor.session_id,
                case_id=assignment.case_id,
                correlation_id=actor.correlation_id,
            ),
        )

    def _record_manual_denial(
        self,
        *,
        actor: ActorContext,
        command,
        now: datetime,
        reason_code: str,
    ) -> None:
        self._reader.record_denial(
            actor=actor,
            command=command,
            now=now,
            reason=reason_code,
        )

    def _resolve_assignment(
        self,
        *,
        tenant_id: UUID,
        membership_id: UUID,
        assignment_id: UUID,
    ) -> AssignmentManagementTarget | None:
        assignment = self._reader.get_assignment(
            tenant_id=tenant_id,
            assignment_id=assignment_id,
        )
        if assignment is None:
            return None
        return assignment if assignment.membership_id == membership_id else None


__all__ = [
    "AssignmentInteractionHandler",
    "AssignmentInteractionService",
    "assignment_handlers",
]

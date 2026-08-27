from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.membership.application.collab_work_task_handler import (
    CollaboratorWorkTaskHandler,
    collaborator_work_task_handlers,
)
from app.modules.membership.application.collab_work_task_ports import (
    CollaboratorTaskProjection,
    CollaboratorWorkTaskReader,
)
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, DispatchResult
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


class CollaboratorWorkTaskService:
    """Authorize bounded collaborator task mutations, then dispatch atomically."""

    def __init__(
        self,
        *,
        reader: CollaboratorWorkTaskReader,
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._reader = reader
        self._dispatcher = dispatcher
        self._policy = policy

    def execute(self, *, actor: ActorContext, command, now: datetime) -> DispatchResult:
        if actor.actor_kind is not ActorKind.COLLABORATEUR:
            self._deny(actor=actor, command=command, now=now, reason="COLLABORATOR_REQUIRED")
            raise PermissionError("COLLABORATOR_REQUIRED")
        if actor.membership_id is None:
            self._deny(actor=actor, command=command, now=now, reason="MEMBERSHIP_REQUIRED")
            raise PermissionError("MEMBERSHIP_REQUIRED")
        candidate_assignment_id = getattr(command, "assignment_id", None)
        assignment_id: UUID | None = (
            candidate_assignment_id if isinstance(candidate_assignment_id, UUID) else None
        )
        if assignment_id is None:
            assignment_id = self._reader.resolve_task_assignment_id(
                tenant_id=actor.tenant_id, task_id=command.task_id
            )
        if assignment_id is None:
            self._deny(actor=actor, command=command, now=now, reason="NOT_FOUND_OR_FORBIDDEN")
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        assignment = self._reader.resolve_assignment(
            tenant_id=actor.tenant_id,
            membership_id=actor.membership_id,
            assignment_id=assignment_id,
        )
        if assignment is None:
            self._deny(actor=actor, command=command, now=now, reason="NOT_FOUND_OR_FORBIDDEN")
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.WORK_TASK_WRITE,
                resource=AuthorizationResource(
                    resource_type="COLLABORATOR_TASK",
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

    def list_for_case(
        self, *, actor: ActorContext, case_id: UUID, now: datetime
    ) -> tuple[CollaboratorTaskProjection, ...]:
        if actor.actor_kind is not ActorKind.COLLABORATEUR or actor.membership_id is None:
            raise PermissionError("COLLABORATOR_REQUIRED")
        assignment = self._reader.resolve_active_assignment_for_case(
            tenant_id=actor.tenant_id,
            membership_id=actor.membership_id,
            case_id=case_id,
        )
        if assignment is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.WORK_TASK_READ,
                resource=AuthorizationResource(
                    resource_type="COLLABORATOR_TASKS",
                    resource_id=assignment.id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)
        return self._reader.list_for_case(
            tenant_id=actor.tenant_id,
            case_id=case_id,
            assignment_id=assignment.id,
        )

    def _deny(self, *, actor: ActorContext, command, now: datetime, reason: str) -> None:
        self._reader.record_denial(actor=actor, command=command, now=now, reason=reason)


__all__ = [
    "CollaboratorTaskProjection",
    "CollaboratorWorkTaskHandler",
    "CollaboratorWorkTaskService",
    "collaborator_work_task_handlers",
]

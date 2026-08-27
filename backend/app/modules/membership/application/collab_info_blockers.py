from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.membership.application.collab_info_blockers_handler import (
    CollaboratorInfoBlockerHandler,
)
from app.modules.membership.application.collab_info_blockers_ports import (
    CollaboratorInfoBlockerReader,
    InformationRequestProjection,
    InformationResponseProjection,
    TaskBlockerProjection,
    TaskProjection,
)
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, DispatchResult
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification

_INFO_BLOCKER_COMMANDS = frozenset(
    {
        "CreateInformationRequest",
        "RecordInformationRequestResponse",
        "DeclareTaskBlocker",
        "ResolveTaskBlocker",
    }
)


class CollaboratorInfoBlockerService:
    """Authorize info/blocker commands against the active task assignment."""

    def __init__(
        self,
        *,
        reader: CollaboratorInfoBlockerReader,
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._reader = reader
        self._dispatcher = dispatcher
        self._policy = policy

    def execute(self, *, actor: ActorContext, command, now: datetime) -> DispatchResult:
        if actor.actor_kind is not ActorKind.COLLABORATEUR or actor.membership_id is None:
            self._deny(actor=actor, command=command, now=now, reason="COLLABORATOR_REQUIRED")
            raise PermissionError("COLLABORATOR_REQUIRED")
        task_id = getattr(command, "task_id", None)
        if task_id is None:
            task_id = self._reader.resolve_task_id(
                tenant_id=actor.tenant_id, request_id=command.request_id
            )
        if task_id is None:
            self._deny(actor=actor, command=command, now=now, reason="NOT_FOUND_OR_FORBIDDEN")
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        assignment = self._reader.resolve_assignment(
            tenant_id=actor.tenant_id,
            membership_id=actor.membership_id,
            task_id=task_id,
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
                    resource_id=task_id,
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

    def read_workflow(
        self, *, actor: ActorContext, task_id: UUID, now: datetime
    ) -> tuple[
        TaskProjection,
        tuple[InformationRequestProjection, ...],
        tuple[InformationResponseProjection, ...],
        tuple[TaskBlockerProjection, ...],
    ]:
        if actor.actor_kind is not ActorKind.COLLABORATEUR or actor.membership_id is None:
            raise PermissionError("COLLABORATOR_REQUIRED")
        assignment = self._reader.resolve_assignment(
            tenant_id=actor.tenant_id,
            membership_id=actor.membership_id,
            task_id=task_id,
        )
        if assignment is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.WORK_TASK_READ,
                resource=AuthorizationResource(
                    resource_type="COLLABORATOR_TASK_WORKFLOW",
                    resource_id=task_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=assignment.case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)
        return self._reader.read_workflow(tenant_id=actor.tenant_id, task_id=task_id)

    def _deny(self, *, actor: ActorContext, command, now: datetime, reason: str) -> None:
        self._reader.record_denial(actor=actor, command=command, now=now, reason=reason)


def collaborator_info_blocker_handlers() -> dict[str, CollaboratorInfoBlockerHandler]:
    handler = CollaboratorInfoBlockerHandler()
    return {command_type: handler for command_type in _INFO_BLOCKER_COMMANDS}

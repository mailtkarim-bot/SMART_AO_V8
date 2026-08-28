"""Patron-owned orchestration for controlled Case assignment management."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.dce.application.commands import (
    AmendCaseAssignmentScopeCommand,
    CreateCaseAssignmentCommand,
    EndCaseAssignmentCommand,
    ReactivateCaseAssignmentCommand,
    SuspendCaseAssignmentCommand,
    ValidateAssignmentInteractionCommand,
)
from app.modules.membership.application.patron_assignment_handler import (
    PatronAssignmentManagementHandler,
    patron_assignment_handlers,
)
from app.modules.membership.application.queries import (
    AssignmentManagementCase,
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


class PatronAssignmentManagementService:
    """Resolve patron authority before dispatching assignment management commands."""

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

    def create(
        self,
        *,
        actor: ActorContext,
        command: CreateCaseAssignmentCommand,
        now: datetime,
    ) -> DispatchResult:
        self._require_patron(
            actor=actor,
            command=command,
            now=now,
            resource_type="CASE",
            resource_id=command.case_id,
            case_id=command.case_id,
        )
        case = self._resolve_case(tenant_id=actor.tenant_id, case_id=command.case_id)
        if case is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
                resource_type="CASE",
                resource_id=command.case_id,
                case_id=command.case_id,
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        self._authorize_case_management(actor=actor, case=case, now=now)
        return self._dispatch(actor=actor, command=command, case_id=case.id, now=now)

    def amend_scope(
        self,
        *,
        actor: ActorContext,
        command: AmendCaseAssignmentScopeCommand,
        now: datetime,
    ) -> DispatchResult:
        self._require_patron(
            actor=actor,
            command=command,
            now=now,
            resource_type="CASE_ASSIGNMENT",
            resource_id=command.assignment_id,
            case_id=None,
        )
        assignment = self._resolve_assignment(
            tenant_id=actor.tenant_id,
            assignment_id=command.assignment_id,
        )
        if assignment is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
                resource_type="CASE_ASSIGNMENT",
                resource_id=command.assignment_id,
                case_id=None,
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.ASSIGNMENT_MANAGE,
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
        return self._dispatch(actor=actor, command=command, case_id=assignment.case_id, now=now)

    def suspend(
        self,
        *,
        actor: ActorContext,
        command: SuspendCaseAssignmentCommand,
        now: datetime,
    ) -> DispatchResult:
        self._require_patron(
            actor=actor,
            command=command,
            now=now,
            resource_type="CASE_ASSIGNMENT",
            resource_id=command.assignment_id,
            case_id=None,
        )
        assignment = self._resolve_assignment(
            tenant_id=actor.tenant_id,
            assignment_id=command.assignment_id,
        )
        if assignment is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
                resource_type="CASE_ASSIGNMENT",
                resource_id=command.assignment_id,
                case_id=None,
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        self._authorize_assignment_management(actor=actor, assignment=assignment, now=now)
        return self._dispatch(actor=actor, command=command, case_id=assignment.case_id, now=now)

    def reactivate(
        self,
        *,
        actor: ActorContext,
        command: ReactivateCaseAssignmentCommand,
        now: datetime,
    ) -> DispatchResult:
        self._require_patron(
            actor=actor,
            command=command,
            now=now,
            resource_type="CASE_ASSIGNMENT",
            resource_id=command.assignment_id,
            case_id=None,
        )
        assignment = self._resolve_assignment(
            tenant_id=actor.tenant_id,
            assignment_id=command.assignment_id,
        )
        if assignment is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
                resource_type="CASE_ASSIGNMENT",
                resource_id=command.assignment_id,
                case_id=None,
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        self._authorize_assignment_management(actor=actor, assignment=assignment, now=now)
        return self._dispatch(actor=actor, command=command, case_id=assignment.case_id, now=now)

    def end(
        self,
        *,
        actor: ActorContext,
        command: EndCaseAssignmentCommand,
        now: datetime,
    ) -> DispatchResult:
        self._require_patron(
            actor=actor,
            command=command,
            now=now,
            resource_type="CASE_ASSIGNMENT",
            resource_id=command.assignment_id,
            case_id=None,
        )
        assignment = self._resolve_assignment(
            tenant_id=actor.tenant_id,
            assignment_id=command.assignment_id,
        )
        if assignment is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
                resource_type="CASE_ASSIGNMENT",
                resource_id=command.assignment_id,
                case_id=None,
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        self._authorize_assignment_management(actor=actor, assignment=assignment, now=now)
        return self._dispatch(actor=actor, command=command, case_id=assignment.case_id, now=now)

    def validate_interaction(
        self,
        *,
        actor: ActorContext,
        command: ValidateAssignmentInteractionCommand,
        now: datetime,
    ) -> DispatchResult:
        self._require_patron(
            actor=actor,
            command=command,
            now=now,
            resource_type="CASE_ASSIGNMENT_INTERACTION_VALIDATION",
            resource_id=command.assignment_id,
            case_id=None,
        )
        assignment = self._resolve_assignment(
            tenant_id=actor.tenant_id,
            assignment_id=command.assignment_id,
        )
        if assignment is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
                resource_type="CASE_ASSIGNMENT_INTERACTION_VALIDATION",
                resource_id=command.assignment_id,
                case_id=None,
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        self._authorize_assignment_management(actor=actor, assignment=assignment, now=now)
        return self._dispatch(actor=actor, command=command, case_id=assignment.case_id, now=now)

    def _dispatch(
        self,
        *,
        actor: ActorContext,
        command,
        case_id: UUID,
        now: datetime,
    ) -> DispatchResult:
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
                case_id=case_id,
                correlation_id=actor.correlation_id,
            ),
        )

    def _require_patron(
        self,
        *,
        actor: ActorContext,
        command,
        now: datetime,
        resource_type: str,
        resource_id: UUID,
        case_id: UUID | None,
    ) -> None:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="ASSIGNMENT_PATRON_REQUIRED",
                resource_type=resource_type,
                resource_id=resource_id,
                case_id=case_id,
            )
            raise PermissionError("ASSIGNMENT_PATRON_REQUIRED")
        if actor.membership_id is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="ASSIGNMENT_MEMBERSHIP_REQUIRED",
                resource_type=resource_type,
                resource_id=resource_id,
                case_id=case_id,
            )
            raise PermissionError("ASSIGNMENT_MEMBERSHIP_REQUIRED")

    def _authorize_case_management(
        self,
        *,
        actor: ActorContext,
        case: AssignmentManagementCase,
        now: datetime,
    ) -> None:
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.ASSIGNMENT_MANAGE,
                resource=AuthorizationResource(
                    resource_type="CASE",
                    resource_id=case.id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=case.id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)

    def _authorize_assignment_management(
        self,
        *,
        actor: ActorContext,
        assignment: AssignmentManagementTarget,
        now: datetime,
    ) -> None:
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.ASSIGNMENT_MANAGE,
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

    def _record_manual_denial(
        self,
        *,
        actor: ActorContext,
        command,
        now: datetime,
        reason_code: str,
        resource_type: str,
        resource_id: UUID,
        case_id: UUID | None,
    ) -> None:
        self._reader.record_denial(
            actor=actor,
            command=command,
            now=now,
            reason=reason_code,
        )

    def _resolve_case(self, *, tenant_id: UUID, case_id: UUID) -> AssignmentManagementCase | None:
        return self._reader.get_case(tenant_id=tenant_id, case_id=case_id)

    def _resolve_assignment(
        self, *, tenant_id: UUID, assignment_id: UUID
    ) -> AssignmentManagementTarget | None:
        return self._reader.get_assignment(tenant_id=tenant_id, assignment_id=assignment_id)


__all__ = [
    "PatronAssignmentManagementHandler",
    "PatronAssignmentManagementService",
    "patron_assignment_handlers",
]

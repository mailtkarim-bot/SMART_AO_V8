"""Single application boundary for membership-owned assignment mutations."""

from __future__ import annotations

from datetime import datetime

from app.modules.dce.application.commands import (
    AcknowledgeAssignmentCommand,
    AmendCaseAssignmentScopeCommand,
    CreateCaseAssignmentCommand,
    EndCaseAssignmentCommand,
    ReactivateCaseAssignmentCommand,
    ReportAssignmentUnavailabilityCommand,
    RequestAssignmentClarificationCommand,
    SuspendCaseAssignmentCommand,
    ValidateAssignmentInteractionCommand,
)
from app.modules.membership.application.assignment import AssignmentInteractionService
from app.modules.membership.application.patron_assignment import (
    PatronAssignmentManagementService,
)
from app.platform.events.dispatcher import DispatchResult
from app.platform.security.context import ActorContext


class MembershipMutationService:
    """Expose one membership mutation boundary for patron and collaborator flows.

    The façade owns no business rule. It keeps the existing role-specific services
    as policy-enforcing components and makes the composition explicit at the
    application boundary used by HTTP adapters and future non-HTTP entrypoints.
    """

    def __init__(
        self,
        *,
        patron_assignments: PatronAssignmentManagementService,
        collaborator_assignments: AssignmentInteractionService,
    ) -> None:
        self._patron_assignments = patron_assignments
        self._collaborator_assignments = collaborator_assignments

    def create(
        self,
        *,
        actor: ActorContext,
        command: CreateCaseAssignmentCommand,
        now: datetime,
    ) -> DispatchResult:
        return self._patron_assignments.create(actor=actor, command=command, now=now)

    def amend_scope(
        self,
        *,
        actor: ActorContext,
        command: AmendCaseAssignmentScopeCommand,
        now: datetime,
    ) -> DispatchResult:
        return self._patron_assignments.amend_scope(actor=actor, command=command, now=now)

    def suspend(
        self,
        *,
        actor: ActorContext,
        command: SuspendCaseAssignmentCommand,
        now: datetime,
    ) -> DispatchResult:
        return self._patron_assignments.suspend(actor=actor, command=command, now=now)

    def reactivate(
        self,
        *,
        actor: ActorContext,
        command: ReactivateCaseAssignmentCommand,
        now: datetime,
    ) -> DispatchResult:
        return self._patron_assignments.reactivate(actor=actor, command=command, now=now)

    def end(
        self,
        *,
        actor: ActorContext,
        command: EndCaseAssignmentCommand,
        now: datetime,
    ) -> DispatchResult:
        return self._patron_assignments.end(actor=actor, command=command, now=now)

    def validate_interaction(
        self,
        *,
        actor: ActorContext,
        command: ValidateAssignmentInteractionCommand,
        now: datetime,
    ) -> DispatchResult:
        return self._patron_assignments.validate_interaction(
            actor=actor,
            command=command,
            now=now,
        )

    def acknowledge(
        self,
        *,
        actor: ActorContext,
        command: AcknowledgeAssignmentCommand,
        now: datetime,
    ) -> DispatchResult:
        return self._collaborator_assignments.acknowledge(actor=actor, command=command, now=now)

    def clarify(
        self,
        *,
        actor: ActorContext,
        command: RequestAssignmentClarificationCommand,
        now: datetime,
    ) -> DispatchResult:
        return self._collaborator_assignments.clarify(actor=actor, command=command, now=now)

    def report_unavailability(
        self,
        *,
        actor: ActorContext,
        command: ReportAssignmentUnavailabilityCommand,
        now: datetime,
    ) -> DispatchResult:
        return self._collaborator_assignments.report_unavailability(
            actor=actor,
            command=command,
            now=now,
        )

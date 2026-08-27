from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.membership.application.collab_capability_commands import (
    ProposeCapabilityForCaseCommand,
    ReportCapabilityGapCommand,
)
from app.modules.membership.application.collab_capability_handler import (
    ProposeCapabilityForCaseHandler,
    ReportCapabilityGapHandler,
)
from app.modules.membership.application.collab_capability_ports import (
    CapabilityGapProjection,
    CapabilityProposalProjection,
    CollaboratorCapabilityAssessmentProjection,
    CollaboratorCapabilityReader,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandHandler,
    DispatchResult,
)
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


class CollaboratorCapabilityAssessmentService:
    """Authorize case capability evidence without owning persistence reads."""

    def __init__(
        self,
        *,
        reader: CollaboratorCapabilityReader,
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._reader = reader
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
            actor=actor,
            command=command,
            now=now,
            action=Capability.PREPARATION_CAPABILITY_PROPOSE,
        )
        return self._dispatcher.dispatch(
            command=command,
            context=self._context(actor=actor, now=now, case_id=command.case_id),
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
            command=command,
            context=self._context(actor=actor, now=now, case_id=command.case_id),
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
            actor=actor,
            case_id=case_id,
            now=now,
            action=Capability.PREPARATION_CAPABILITY_PROPOSE,
        )
        self._reader.require_active_assignment(
            tenant_id=actor.tenant_id,
            membership_id=self._membership_id(actor),
            case_id=case_id,
            assignment_id=assignment_id,
            required_action=Capability.PREPARATION_CAPABILITY_PROPOSE.value,
            received_at=now,
        )
        return self._reader.read_assessments(
            tenant_id=actor.tenant_id,
            case_id=case_id,
            assignment_id=assignment_id,
        )

    def _preflight_assignment(
        self, *, actor: ActorContext, command, now: datetime, action: Capability
    ) -> None:
        self._reader.require_active_assignment(
            tenant_id=actor.tenant_id,
            membership_id=self._membership_id(actor),
            case_id=command.case_id,
            assignment_id=command.assignment_id,
            required_action=action.value,
            received_at=now,
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
    def _membership_id(actor: ActorContext) -> UUID:
        if actor.membership_id is None:
            raise PermissionError("COLLABORATOR_REQUIRED")
        return actor.membership_id

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


def collaborator_capability_handlers() -> dict[str, CommandHandler]:
    return {
        "ProposeCapabilityForCase": ProposeCapabilityForCaseHandler(),
        "ReportCapabilityGap": ReportCapabilityGapHandler(),
    }


__all__ = [
    "CapabilityGapProjection",
    "CapabilityProposalProjection",
    "CollaboratorCapabilityAssessmentProjection",
    "CollaboratorCapabilityAssessmentService",
    "collaborator_capability_handlers",
]

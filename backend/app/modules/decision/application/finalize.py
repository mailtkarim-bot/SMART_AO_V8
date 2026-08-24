from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.modules.decision.application.finalize_commands import FinalizeGoNoGoDecisionCommand
from app.modules.decision.application.ports import (
    DecisionRepository,
    DecisionVerifiedContextReader,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
    DispatchResult,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.persistence.repository import OptimisticRevisionConflictError
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


class PatronDecisionFinalizationService:
    """Authorize and dispatch a human GO/NO-GO finalization."""

    def __init__(self, *, dispatcher: CommandDispatcher, policy: AuthorizationPolicyPort) -> None:
        self._dispatcher = dispatcher
        self._policy = policy

    def execute(
        self,
        *,
        actor: ActorContext,
        command: FinalizeGoNoGoDecisionCommand,
        now: datetime,
    ) -> DispatchResult:
        if actor.actor_kind not in {ActorKind.PATRON_ADMIN, ActorKind.PATRON_DELEGATE}:
            raise PermissionError("PATRON_REQUIRED")
        if actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.DECISION_FINALIZE,
                resource=AuthorizationResource(
                    resource_type="DECISION",
                    resource_id=command.decision_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=command.case_id,
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
                case_id=command.case_id,
                correlation_id=actor.correlation_id,
            ),
        )


class FinalizeGoNoGoDecisionHandler:
    """Finalize only a current, frozen, patron-reviewed Decision context."""

    def __init__(
        self,
        *,
        repository_factory: Callable[[Any], DecisionRepository],
        verified_context_reader: DecisionVerifiedContextReader,
    ) -> None:
        self._repository_factory = repository_factory
        self._verified_context_reader = verified_context_reader

    def execute(self, *, session: Any, command, context: CommandContext) -> HandlerOutcome:
        if context.actor_kind not in {
            ActorKind.PATRON_ADMIN.value,
            ActorKind.PATRON_DELEGATE.value,
        } or context.membership_id is None:
            raise CommandExecutionError("PATRON_REQUIRED")
        repository = self._repository_factory(session)
        snapshot = repository.get(
            tenant_id=context.tenant_id,
            aggregate_id=command.decision_id,
        )
        if snapshot is None or snapshot.root.case_id != command.case_id:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        root = snapshot.root
        if (
            root.decision_type != "GO_NO_GO"
            or root.lifecycle != "PENDING_PATRON"
            or root.outcome != "UNDECIDED"
            or root.validity != "CURRENT"
            or root.context_status != "FROZEN"
        ):
            raise CommandExecutionError("DECISION_NOT_READY_FOR_FINALIZATION")
        if not snapshot.contexts:
            raise CommandExecutionError("DECISION_CONTEXT_REQUIRED")
        current_context = snapshot.contexts[-1]
        if (
            current_context.context_state != "FROZEN"
            or current_context.context_fingerprint.lower() != command.displayed_fingerprint.lower()
        ):
            raise CommandExecutionError("STALE_DECISION_CONTEXT")
        if not snapshot.context_references:
            raise CommandExecutionError("DECISION_CONTEXT_REFERENCES_REQUIRED")
        if not self._verified_context_reader.has_confirmed_dce_requirements(
            session=session,
            tenant_id=context.tenant_id,
            context_id=current_context.id,
            case_id=command.case_id,
        ):
            raise CommandExecutionError("DCE_REQUIREMENTS_NOT_CONFIRMED")

        try:
            new_revision = repository.update_root(
                tenant_id=context.tenant_id,
                aggregate_id=command.decision_id,
                expected_revision=command.expected_revision,
                changes={
                    "lifecycle": "FINALIZED",
                    "outcome": command.outcome,
                    "validity": "CURRENT",
                    "condition_status": "NOT_APPLICABLE",
                    "context_status": "FROZEN",
                    "selected_final_context_id": current_context.id,
                    "final_justification": command.justification.strip(),
                    "finalized_by_actor_id": context.actor_id,
                    "finalized_at": context.received_at,
                    "updated_by_actor_id": context.actor_id,
                },
            )
        except OptimisticRevisionConflictError as error:
            raise CommandExecutionError("STALE_DECISION_REVISION") from error
        return HandlerOutcome(
            result_code="DECISION_FINALIZED",
            aggregate_refs=(
                {
                    "aggregate_type": "Decision",
                    "aggregate_id": str(command.decision_id),
                    "aggregate_revision": new_revision,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="Decision",
                    aggregate_id=command.decision_id,
                    aggregate_revision=new_revision,
                    event_type="DecisionFinalized",
                    payload={
                        "decision_id": str(command.decision_id),
                        "case_id": str(command.case_id),
                        "outcome": command.outcome,
                        "aggregate_revision": new_revision,
                    },
                ),
            ),
        )


def decision_finalization_handlers(
    *,
    repository_factory: Callable[[Any], DecisionRepository],
    verified_context_reader: DecisionVerifiedContextReader,
) -> dict[str, object]:
    return {
        FinalizeGoNoGoDecisionCommand.command_type: FinalizeGoNoGoDecisionHandler(
            repository_factory=repository_factory,
            verified_context_reader=verified_context_reader,
        )
    }

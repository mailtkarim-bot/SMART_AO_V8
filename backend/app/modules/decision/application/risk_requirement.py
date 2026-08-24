from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.decision.application.link_commands import LinkRiskToRequirementCommand
from app.modules.decision.application.ports import (
    DecisionPatronActionWriter,
    DecisionRiskRequirementLinkDraft,
    DecisionRiskRequirementLinkRepository,
)
from app.modules.decision.domain.risk_requirement import (
    RiskRequirementLink,
    RiskRequirementRelation,
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


class PatronDecisionRiskRequirementService:
    """Authorize and dispatch a patron link to a confirmed DCE requirement."""

    def __init__(self, *, dispatcher: CommandDispatcher, policy: AuthorizationPolicyPort) -> None:
        self._dispatcher = dispatcher
        self._policy = policy

    def execute(
        self,
        *,
        actor: ActorContext,
        command: LinkRiskToRequirementCommand,
        now: datetime,
    ) -> DispatchResult:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.DECISION_RISK_LINK_WRITE,
                resource=AuthorizationResource(
                    resource_type="CASE_RISK_REQUIREMENT_LINK",
                    resource_id=command.link_id,
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


class LinkRiskToRequirementHandler:
    """Validate context and append one immutable, confirmed link."""

    def __init__(
        self,
        *,
        repository_factory: Callable[[Any], DecisionRiskRequirementLinkRepository],
        action_writer: DecisionPatronActionWriter | None = None,
    ) -> None:
        self._repository_factory = repository_factory
        self._action_writer = action_writer

    def execute(self, *, session: Any, command, context: CommandContext) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("PATRON_REQUIRED")
        repository = self._repository_factory(session)
        if not repository.case_exists(
            session=session, tenant_id=context.tenant_id, case_id=command.case_id
        ):
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if not repository.case_uses_dce_version(
            session=session,
            tenant_id=context.tenant_id,
            case_id=command.case_id,
            dce_version_id=command.dce_version_id,
        ):
            raise CommandExecutionError("STALE_DCE_CONTEXT")
        if not repository.risk_matches_case_and_version(
            session=session,
            tenant_id=context.tenant_id,
            risk_id=command.risk_id,
            case_id=command.case_id,
            dce_version_id=command.dce_version_id,
        ):
            raise CommandExecutionError("RISK_NOT_FOUND_OR_FORBIDDEN")
        if not repository.requirement_is_confirmed(
            session=session,
            tenant_id=context.tenant_id,
            requirement_id=command.requirement_id,
            dce_version_id=command.dce_version_id,
        ):
            raise CommandExecutionError("DCE_REQUIREMENT_NOT_CONFIRMED")

        link = RiskRequirementLink(
            risk_id=command.risk_id,
            requirement_id=command.requirement_id,
            relationship=RiskRequirementRelation(command.relationship),
            rationale=command.rationale,
        )
        link.validate()
        functional_key = ":".join(
            (
                str(command.case_id),
                str(command.dce_version_id),
                str(command.risk_id),
                str(command.requirement_id),
                command.relationship,
            )
        )
        if repository.functional_exists(
            session=session, tenant_id=context.tenant_id, functional_key=functional_key
        ):
            raise CommandExecutionError("RISK_REQUIREMENT_LINK_ALREADY_EXISTS")
        repository.create(
            session=session,
            draft=DecisionRiskRequirementLinkDraft(
                id=command.link_id,
                tenant_id=context.tenant_id,
                case_id=command.case_id,
                risk_id=command.risk_id,
                requirement_id=command.requirement_id,
                dce_version_id=command.dce_version_id,
                functional_key=functional_key,
                link=link,
                actor_id=context.actor_id,
                membership_id=context.membership_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=context.correlation_id,
            ),
        )
        aggregate_refs: list[dict[str, object]] = [
            {
                "aggregate_type": "DecisionRiskRequirementLink",
                "aggregate_id": str(command.link_id),
                "aggregate_revision": 1,
            }
        ]
        events = [
            PendingDomainEvent(
                aggregate_type="DecisionRiskRequirementLink",
                aggregate_id=command.link_id,
                aggregate_revision=1,
                event_type="DecisionRiskRequirementLinked",
                payload={
                    "link_id": str(command.link_id),
                    "case_id": str(command.case_id),
                    "risk_id": str(command.risk_id),
                    "requirement_id": str(command.requirement_id),
                    "relationship": command.relationship,
                },
            )
        ]
        if self._action_writer is not None:
            action_ref = self._action_writer.create_from_risk_requirement_link(
                session=session,
                context=context,
                case_id=command.case_id,
                risk_id=command.risk_id,
                requirement_id=command.requirement_id,
                link_id=command.link_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
            )
            if action_ref is not None:
                action_id = UUID(str(action_ref.id))
                action_revision = int(action_ref.aggregate_revision)
                aggregate_refs.append(
                    {
                        "aggregate_type": "PatronAction",
                        "aggregate_id": str(action_id),
                        "aggregate_revision": action_revision,
                    }
                )
                events.append(
                    PendingDomainEvent(
                        aggregate_type="PatronAction",
                        aggregate_id=action_id,
                        aggregate_revision=action_revision,
                        event_type="PatronActionCreated",
                        payload={
                            "action_id": str(action_id),
                            "case_id": str(command.case_id),
                            "action_type": "DECIDE_GO_NO_GO",
                            "severity": "BLOCKING",
                            "state": "OPEN",
                        },
                    )
                )
        return HandlerOutcome(
            result_code="DECISION_RISK_REQUIREMENT_LINKED",
            aggregate_refs=tuple(aggregate_refs),
            events=tuple(events),
        )


def decision_risk_requirement_link_handlers(
    *,
    repository_factory: Callable[[Any], DecisionRiskRequirementLinkRepository],
    action_writer: DecisionPatronActionWriter | None = None,
) -> dict[str, object]:
    return {
        LinkRiskToRequirementCommand.command_type: LinkRiskToRequirementHandler(
            repository_factory=repository_factory,
            action_writer=action_writer,
        )
    }

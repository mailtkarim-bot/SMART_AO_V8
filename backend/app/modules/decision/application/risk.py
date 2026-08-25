from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.decision.application.ports import DecisionRiskDraft, DecisionRiskRepository
from app.modules.decision.application.risk_commands import RegisterStructuredRiskCommand
from app.modules.decision.domain.risk import (
    RiskCategory,
    RiskLikelihood,
    RiskSeverity,
    RiskTreatment,
    StructuredRisk,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
    CommandHandler,
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


class PatronDecisionRiskService:
    """Authorize and dispatch patron registration of one structured DCE risk."""

    def __init__(self, *, dispatcher: CommandDispatcher, policy: AuthorizationPolicyPort) -> None:
        self._dispatcher = dispatcher
        self._policy = policy

    def execute(
        self,
        *,
        actor: ActorContext,
        command: RegisterStructuredRiskCommand,
        now: datetime,
    ) -> DispatchResult:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.DECISION_RISK_WRITE,
                resource=AuthorizationResource(
                    resource_type="CASE_RISK_REGISTER",
                    resource_id=command.case_id,
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


class RegisterStructuredRiskHandler:
    """Validate provenance and append one immutable structured risk."""

    def __init__(
        self,
        *,
        repository_factory: Callable[[Any], DecisionRiskRepository],
    ) -> None:
        self._repository_factory = repository_factory

    def execute(self, *, session: Any, command, context: CommandContext) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("PATRON_REQUIRED")
        tenant_id = UUID(str(context.tenant_id))
        actor_id = UUID(str(context.actor_id))
        membership_id = UUID(str(context.membership_id))
        correlation_id = UUID(str(context.correlation_id)) if context.correlation_id else None
        repository = self._repository_factory(session)
        if not repository.case_exists(
            session=session, tenant_id=tenant_id, case_id=command.case_id
        ):
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if not repository.case_uses_dce_version(
            session=session,
            tenant_id=tenant_id,
            case_id=command.case_id,
            dce_version_id=command.dce_version_id,
        ):
            raise CommandExecutionError("STALE_DCE_CONTEXT")
        if not repository.source_exists(
            session=session,
            tenant_id=tenant_id,
            dce_version_id=command.dce_version_id,
            source_fragment_id=command.source_fragment_id,
        ):
            raise CommandExecutionError("SOURCE_FRAGMENT_NOT_FOUND_OR_FORBIDDEN")
        if not repository.source_supports(
            session=session,
            tenant_id=tenant_id,
            dce_version_id=command.dce_version_id,
            source_fragment_id=command.source_fragment_id,
            source_excerpt=command.source_excerpt,
            start_byte_offset=command.start_byte_offset,
            end_byte_offset=command.end_byte_offset,
        ):
            raise CommandExecutionError("SOURCE_PROVENANCE_MISMATCH")
        risk = StructuredRisk(
            category=RiskCategory(command.category),
            risk_code=command.risk_code,
            title=command.title,
            statement=command.statement,
            severity=RiskSeverity(command.severity),
            likelihood=RiskLikelihood(command.likelihood),
            treatment=RiskTreatment.OPEN,
            source_excerpt=command.source_excerpt,
            start_byte_offset=command.start_byte_offset,
            end_byte_offset=command.end_byte_offset,
            source_locator=command.source_locator,
        )
        risk.validate()
        functional_key = ":".join(
            (
                str(command.case_id),
                str(command.dce_version_id),
                str(command.source_fragment_id),
                command.risk_code,
            )
        )
        if repository.functional_exists(
            session=session, tenant_id=tenant_id, functional_key=functional_key
        ):
            raise CommandExecutionError("RISK_ALREADY_REGISTERED")
        draft = DecisionRiskDraft(
            id=command.risk_id,
            tenant_id=tenant_id,
            case_id=command.case_id,
            dce_version_id=command.dce_version_id,
            source_fragment_id=command.source_fragment_id,
            functional_key=functional_key,
            risk=risk,
            actor_id=actor_id,
            membership_id=membership_id,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=correlation_id,
            due_at=command.due_at,
        )
        repository.create(session=session, draft=draft)
        return HandlerOutcome(
            result_code="DECISION_RISK_REGISTERED",
            aggregate_refs=(
                {
                    "aggregate_type": "DecisionRisk",
                    "aggregate_id": str(command.risk_id),
                    "aggregate_revision": 1,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="DecisionRisk",
                    aggregate_id=command.risk_id,
                    aggregate_revision=1,
                    event_type="DecisionRiskRegistered",
                    payload={
                        "risk_id": str(command.risk_id),
                        "case_id": str(command.case_id),
                        "category": command.category,
                        "severity": command.severity,
                    },
                ),
            ),
        )


def decision_risk_handlers(
    *, repository_factory: Callable[[Any], DecisionRiskRepository]
) -> dict[str, CommandHandler]:
    return {
        RegisterStructuredRiskCommand.command_type: RegisterStructuredRiskHandler(
            repository_factory=repository_factory
        )
    }

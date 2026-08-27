from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.pricing.application.queries import PricingScenarioProjection, PricingScenarioReader
from app.modules.pricing.application.transition_commands import (
    ArchivePricingScenarioCommand,
    SelectPricingScenarioCommand,
    TransitionPricingScenarioCommand,
)
from app.modules.pricing.infrastructure.models import (
    PricingScenarioRecord,
    PricingScenarioTransitionRecord,
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


class PricingScenarioTransitionService:
    def __init__(
        self,
        *,
        reader: PricingScenarioReader,
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._reader = reader
        self._dispatcher = dispatcher
        self._policy = policy

    def execute(
        self, *, actor: ActorContext, command: TransitionPricingScenarioCommand, now: datetime
    ) -> DispatchResult:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.PRICING_WRITE,
                resource=AuthorizationResource(
                    resource_type="PRICING_SCENARIO",
                    resource_id=command.scenario_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.FINANCIAL_PRIVATE,
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
                correlation_id=actor.correlation_id,
            ),
        )

    def list_for_case(self, *, actor: ActorContext, case_id, now: datetime):
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        return self._reader.list_for_case(tenant_id=actor.tenant_id, case_id=case_id)


class TransitionPricingScenarioHandler:
    def execute(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        scenario = session.scalar(
            sa.select(PricingScenarioRecord)
            .where(
                PricingScenarioRecord.tenant_id == context.tenant_id,
                PricingScenarioRecord.id == command.scenario_id,
            )
            .with_for_update()
        )
        if scenario is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        latest = session.scalar(
            sa.select(PricingScenarioTransitionRecord)
            .where(
                PricingScenarioTransitionRecord.tenant_id == context.tenant_id,
                PricingScenarioTransitionRecord.scenario_id == scenario.id,
            )
            .order_by(PricingScenarioTransitionRecord.version.desc())
            .limit(1)
        )
        current_state = latest.to_state if latest is not None else scenario.state
        current_version = latest.version if latest is not None else scenario.version
        if current_version != command.expected_version:
            raise CommandExecutionError("VERSION_CONFLICT")
        if current_state == "ARCHIVED":
            raise CommandExecutionError("SCENARIO_ALREADY_ARCHIVED")
        if command.target_state == current_state:
            raise CommandExecutionError("INVALID_STATE_TRANSITION")
        if command.target_state == "SELECTED":
            siblings = session.scalars(
                sa.select(PricingScenarioRecord)
                .where(
                    PricingScenarioRecord.tenant_id == context.tenant_id,
                    PricingScenarioRecord.case_id == scenario.case_id,
                    PricingScenarioRecord.id != scenario.id,
                )
                .with_for_update()
            ).all()
            for sibling in siblings:
                sibling_latest = session.scalar(
                    sa.select(PricingScenarioTransitionRecord)
                    .where(
                        PricingScenarioTransitionRecord.tenant_id == context.tenant_id,
                        PricingScenarioTransitionRecord.scenario_id == sibling.id,
                    )
                    .order_by(PricingScenarioTransitionRecord.version.desc())
                    .limit(1)
                )
                sibling_state = (
                    sibling_latest.to_state if sibling_latest is not None else sibling.state
                )
                if sibling_state == "SELECTED":
                    raise CommandExecutionError("SCENARIO_ALREADY_SELECTED")
        transition = PricingScenarioTransitionRecord(
            id=command.transition_id,
            tenant_id=context.tenant_id,
            scenario_id=scenario.id,
            from_state=current_state,
            to_state=command.target_state,
            reason_code=command.reason_code,
            version=current_version + 1,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )
        session.add(transition)
        return HandlerOutcome(
            result_code="PRICING_SCENARIO_TRANSITIONED",
            aggregate_refs=({
                "aggregate_type": "PricingScenario",
                "aggregate_id": str(scenario.id),
                "aggregate_revision": transition.version,
            },),
            events=(PendingDomainEvent(
                aggregate_type="PricingScenario",
                aggregate_id=scenario.id,
                aggregate_revision=transition.version,
                event_type="PricingScenarioTransitioned",
                payload={
                    "scenario_id": str(scenario.id),
                    "from_state": current_state,
                    "to_state": command.target_state,
                    "version": transition.version,
                },
            ),),
        )


def pricing_scenario_transition_handlers():
    handler = TransitionPricingScenarioHandler()
    return {
        TransitionPricingScenarioCommand.command_type: handler,
        SelectPricingScenarioCommand.command_type: handler,
        ArchivePricingScenarioCommand.command_type: handler,
    }


def _projection(record: PricingScenarioRecord) -> PricingScenarioProjection:
    return PricingScenarioProjection(
        scenario_id=record.id,
        case_id=record.case_id,
        scenario_key=record.scenario_key,
        scenario_type=record.scenario_type,
        version=record.version,
        state=record.state,
        assumptions=record.assumptions_json,
        sales_total_minor=record.sales_total_minor,
        total_cost_minor=record.total_cost_minor,
        gross_margin_minor=record.gross_margin_minor,
        gross_margin_rate_bps=record.gross_margin_rate_bps,
        penalty_reserve_minor=record.penalty_reserve_minor,
        retention_reserve_minor=record.retention_reserve_minor,
        guarantee_reserve_minor=record.guarantee_reserve_minor,
        floor_margin_rate_bps=record.floor_margin_rate_bps,
        target_margin_rate_bps=record.target_margin_rate_bps,
        break_even_sales_minor=record.break_even_sales_minor,
        floor_sales_minor=record.floor_sales_minor,
        target_sales_minor=record.target_sales_minor,
        source_snapshot_revision=record.source_snapshot_revision,
    )

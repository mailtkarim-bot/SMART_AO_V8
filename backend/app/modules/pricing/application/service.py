from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.pricing.application.commands import CreatePricingScenarioCommand
from app.modules.pricing.domain.scenario import calculate_pricing_scenario_amounts
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
from app.platform.security.models import FinancialReportSnapshotRecord, PricingScenarioRecord


@dataclass(frozen=True, slots=True)
class PricingScenarioProjection:
    scenario_id: UUID
    case_id: UUID
    scenario_key: str
    scenario_type: str
    version: int
    state: str
    assumptions: dict[str, object]
    sales_total_minor: int
    total_cost_minor: int
    gross_margin_minor: int
    gross_margin_rate_bps: int
    source_snapshot_revision: int


class PricingScenarioService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._policy = policy

    def execute(self, *, actor: ActorContext, command, now: datetime) -> DispatchResult:
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

    def list_for_case(self, *, actor: ActorContext, case_id: UUID, now: datetime):
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        with self._session_factory() as session:
            return tuple(
                _projection(row)
                for row in session.scalars(
                    sa.select(PricingScenarioRecord)
                    .where(
                        PricingScenarioRecord.tenant_id == actor.tenant_id,
                        PricingScenarioRecord.case_id == case_id,
                    )
                    .order_by(PricingScenarioRecord.created_at.desc())
                ).all()
            )


class PricingScenarioHandler:
    def execute(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("PATRON_REQUIRED")
        snapshot = session.scalar(
            sa.select(FinancialReportSnapshotRecord).where(
                FinancialReportSnapshotRecord.tenant_id == context.tenant_id,
                FinancialReportSnapshotRecord.id == command.source_snapshot_id,
                FinancialReportSnapshotRecord.case_id == command.case_id,
                FinancialReportSnapshotRecord.state == "PUBLISHED",
            )
        )
        if snapshot is None:
            raise CommandExecutionError("OFFICIAL_PRICE_NOT_PUBLISHED")
        version = (
            session.scalar(
                sa.select(sa.func.coalesce(sa.func.max(PricingScenarioRecord.version), 0)).where(
                    PricingScenarioRecord.tenant_id == context.tenant_id,
                    PricingScenarioRecord.case_id == command.case_id,
                    PricingScenarioRecord.scenario_key == command.scenario_key,
                )
            )
            + 1
        )
        amounts = calculate_pricing_scenario_amounts(
            sales_total_minor=snapshot.sales_total_minor,
            direct_cost_total_minor=snapshot.direct_cost_total_minor,
            overhead_total_minor=snapshot.overhead_total_minor,
            subcontracting_total_minor=snapshot.subcontracting_total_minor,
            contingency_total_minor=snapshot.contingency_total_minor,
            sales_adjustment_bps=command.sales_adjustment_bps,
            cost_adjustment_bps=command.cost_adjustment_bps,
        )
        record = PricingScenarioRecord(
            id=command.scenario_id,
            tenant_id=context.tenant_id,
            case_id=command.case_id,
            source_snapshot_id=snapshot.id,
            scenario_key=command.scenario_key,
            scenario_type=command.scenario_type,
            version=version,
            state="DRAFT",
            assumptions_json=command.assumptions,
            sales_total_minor=amounts.sales_total_minor,
            total_cost_minor=amounts.total_cost_minor,
            gross_margin_minor=amounts.gross_margin_minor,
            gross_margin_rate_bps=amounts.gross_margin_rate_bps,
            source_snapshot_revision=snapshot.aggregate_revision,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )
        session.add(record)
        return HandlerOutcome(
            result_code="PRICING_SCENARIO_CREATED",
            aggregate_refs=(
                {
                    "aggregate_type": "PricingScenario",
                    "aggregate_id": str(record.id),
                    "aggregate_revision": record.version,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="PricingScenario",
                    aggregate_id=record.id,
                    aggregate_revision=record.version,
                    event_type="PricingScenarioCreated",
                    payload={
                        "scenario_id": str(record.id),
                        "case_id": str(record.case_id),
                        "version": record.version,
                    },
                ),
            ),
        )


def pricing_scenario_handlers():
    handler = PricingScenarioHandler()
    return {CreatePricingScenarioCommand.command_type: handler}


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
        source_snapshot_revision=record.source_snapshot_revision,
    )

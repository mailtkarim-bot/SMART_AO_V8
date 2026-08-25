"""Patron-only append of revisioned financial lines to a DRAFT snapshot."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.dce.application.commands import AddFinancialReportLineCommand
from app.modules.pricing.infrastructure.models import (
    FinancialReportLineRecord,
    FinancialReportSnapshotRecord,
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

_CATEGORY_TOTAL_FIELDS = {
    "SALES": "sales_total_minor",
    "DIRECT_COST": "direct_cost_total_minor",
    "OVERHEAD": "overhead_total_minor",
    "SUBCONTRACTING": "subcontracting_total_minor",
    "CONTINGENCY": "contingency_total_minor",
    "GROSS_MARGIN": "gross_margin_minor",
    "FORECAST_CASHFLOW": "forecast_cashflow_minor",
}


class PatronFinancialReportLineService:
    """Authorize a patron before resolving or mutating a financial snapshot."""

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

    def add_line(
        self,
        *,
        actor: ActorContext,
        command: AddFinancialReportLineCommand,
        now: datetime,
    ) -> DispatchResult:
        # Absolute financial confidentiality: do not resolve the snapshot before this guard.
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("FINANCIAL_REPORT_PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.FINANCIAL_REPORT_LINE_WRITE,
                resource=AuthorizationResource(
                    resource_type="CASE_FINANCIAL_REPORT",
                    resource_id=command.report_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.FINANCIAL_PRIVATE,
                    case_id=command.case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)
        with self._session_factory() as session:
            exists = session.scalar(
                sa.select(FinancialReportSnapshotRecord.id).where(
                    FinancialReportSnapshotRecord.tenant_id == actor.tenant_id,
                    FinancialReportSnapshotRecord.case_id == command.case_id,
                    FinancialReportSnapshotRecord.id == command.report_id,
                )
            )
        if exists is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
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


class AddFinancialReportLineHandler:
    """Append one line while holding the snapshot row lock."""

    def execute(
        self,
        *,
        session: Session,
        command: AddFinancialReportLineCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("FINANCIAL_REPORT_PATRON_REQUIRED")
        snapshot = session.scalar(
            sa.select(FinancialReportSnapshotRecord)
            .where(
                FinancialReportSnapshotRecord.tenant_id == context.tenant_id,
                FinancialReportSnapshotRecord.case_id == command.case_id,
                FinancialReportSnapshotRecord.id == command.report_id,
            )
            .with_for_update()
        )
        if snapshot is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if snapshot.state != "DRAFT":
            raise CommandExecutionError("FINANCIAL_REPORT_NOT_DRAFT")
        if snapshot.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("VERSION_CONFLICT")

        line_id = uuid4()
        session.add(
            FinancialReportLineRecord(
                id=line_id,
                tenant_id=context.tenant_id,
                snapshot_id=snapshot.id,
                category=command.category,
                label=command.label,
                quantity_decimal=command.quantity_decimal,
                unit=command.unit,
                amount_minor=command.amount_minor,
            )
        )
        total_field = _CATEGORY_TOTAL_FIELDS[command.category]
        setattr(snapshot, total_field, getattr(snapshot, total_field) + command.amount_minor)
        revision = snapshot.aggregate_revision + 1
        snapshot.aggregate_revision = revision
        snapshot.calculated_at = context.received_at

        return HandlerOutcome(
            result_code="FINANCIAL_REPORT_LINE_ADDED",
            aggregate_refs=(
                {
                    "aggregate_type": "FinancialReportSnapshot",
                    "aggregate_id": str(snapshot.id),
                    "aggregate_revision": revision,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="FinancialReportSnapshot",
                    aggregate_id=snapshot.id,
                    aggregate_revision=revision,
                    event_type="FinancialReportLineAdded",
                    payload={
                        "report_id": str(snapshot.id),
                        "case_id": str(snapshot.case_id),
                        "line_id": str(line_id),
                        "category": command.category,
                        "resulting_revision": revision,
                    },
                ),
            ),
        )


def financial_report_line_handlers() -> dict[str, AddFinancialReportLineHandler]:
    """Return the closed dispatcher registry for financial line writes."""

    return {"AddFinancialReportLine": AddFinancialReportLineHandler()}

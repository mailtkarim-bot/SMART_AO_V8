"""Transactional handler for patron financial report line writes."""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.dce.application.commands import AddFinancialReportLineCommand
from app.modules.pricing.infrastructure.models import (
    FinancialReportLineRecord,
    FinancialReportSnapshotRecord,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandExecutionError,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.security.context import ActorKind

_CATEGORY_TOTAL_FIELDS = {
    "SALES": "sales_total_minor",
    "DIRECT_COST": "direct_cost_total_minor",
    "OVERHEAD": "overhead_total_minor",
    "SUBCONTRACTING": "subcontracting_total_minor",
    "CONTINGENCY": "contingency_total_minor",
    "GROSS_MARGIN": "gross_margin_minor",
    "FORECAST_CASHFLOW": "forecast_cashflow_minor",
}


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

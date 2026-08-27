"""Transactional handler for patron financial report draft creation."""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.commands import CreateFinancialReportDraftCommand
from app.modules.pricing.infrastructure.models import FinancialReportSnapshotRecord
from app.platform.events.dispatcher import (
    CommandContext,
    CommandExecutionError,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.security.context import ActorKind


class CreateFinancialReportDraftHandler:
    """Create one empty DRAFT while holding the owning Case row lock."""

    def execute(
        self,
        *,
        session: Session,
        command: CreateFinancialReportDraftCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("FINANCIAL_REPORT_PATRON_REQUIRED")
        case = session.scalar(
            sa.select(CaseRecord)
            .where(
                CaseRecord.tenant_id == context.tenant_id,
                CaseRecord.id == command.case_id,
            )
            .with_for_update()
        )
        if case is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        existing_draft = session.scalar(
            sa.select(FinancialReportSnapshotRecord.id).where(
                FinancialReportSnapshotRecord.tenant_id == context.tenant_id,
                FinancialReportSnapshotRecord.case_id == command.case_id,
                FinancialReportSnapshotRecord.state == "DRAFT",
            )
        )
        if existing_draft is not None:
            raise CommandExecutionError("FINANCIAL_REPORT_DRAFT_ALREADY_OPEN")

        report_id = uuid4()
        session.add(
            FinancialReportSnapshotRecord(
                id=report_id,
                tenant_id=context.tenant_id,
                case_id=command.case_id,
                state="DRAFT",
                currency_code=command.currency_code,
                ruleset_version=command.ruleset_version,
                aggregate_revision=0,
                calculated_at=context.received_at,
                published_at=None,
                sales_total_minor=0,
                direct_cost_total_minor=0,
                overhead_total_minor=0,
                subcontracting_total_minor=0,
                contingency_total_minor=0,
                gross_margin_minor=0,
                gross_margin_rate_bps=0,
                forecast_cashflow_minor=0,
            )
        )
        return HandlerOutcome(
            result_code="FINANCIAL_REPORT_DRAFT_CREATED",
            aggregate_refs=(
                {
                    "aggregate_type": "FinancialReportSnapshot",
                    "aggregate_id": str(report_id),
                    "aggregate_revision": 0,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="FinancialReportSnapshot",
                    aggregate_id=report_id,
                    aggregate_revision=0,
                    event_type="FinancialReportDraftCreated",
                    payload={
                        "report_id": str(report_id),
                        "case_id": str(command.case_id),
                        "state": "DRAFT",
                        "resulting_revision": 0,
                    },
                ),
            ),
        )

"""Transactional handler for patron financial report publication."""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.dce.application.commands import PublishFinancialReportCommand
from app.modules.pricing.infrastructure.models import (
    FinancialReportPublicationRecord,
    FinancialReportSnapshotRecord,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandExecutionError,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.security.context import ActorKind


class PublishFinancialReportHandler:
    """Execute the publication act under a snapshot row lock."""

    def execute(
        self,
        *,
        session: Session,
        command: PublishFinancialReportCommand,
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

        revision = snapshot.aggregate_revision + 1
        snapshot.state = "PUBLISHED"
        snapshot.published_at = context.received_at
        snapshot.aggregate_revision = revision
        session.add(
            FinancialReportPublicationRecord(
                id=uuid4(),
                tenant_id=context.tenant_id,
                snapshot_id=snapshot.id,
                patron_membership_id=context.membership_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
                published_at=context.received_at,
            )
        )
        return HandlerOutcome(
            result_code="FINANCIAL_REPORT_PUBLISHED",
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
                    event_type="FinancialReportPublished",
                    payload={
                        "report_id": str(snapshot.id),
                        "case_id": str(snapshot.case_id),
                        "resulting_revision": revision,
                    },
                ),
            ),
        )

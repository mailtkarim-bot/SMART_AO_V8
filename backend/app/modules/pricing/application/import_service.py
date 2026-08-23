from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.pricing.application.import_commands import CommitPricingImportCommand
from app.modules.pricing.infrastructure.models import (
    FinancialReportLineRecord,
    FinancialReportSnapshotRecord,
    PricingImportBatchRecord,
    PricingImportRowRecord,
    PricingImportTransitionRecord,
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


class PricingImportService:
    """Authorize and dispatch one patronal application of normalized import rows."""

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

    def commit(
        self,
        *,
        actor: ActorContext,
        command: CommitPricingImportCommand,
        now: datetime,
    ) -> DispatchResult:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("FINANCIAL_REPORT_PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.FINANCIAL_REPORT_LINE_WRITE,
                resource=AuthorizationResource(
                    resource_type="PRICING_IMPORT",
                    resource_id=command.batch_id,
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


class CommitPricingImportHandler:
    """Apply valid normalized rows to one unlocked financial draft atomically."""

    def execute(
        self,
        *,
        session: Session,
        command: CommitPricingImportCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("FINANCIAL_REPORT_PATRON_REQUIRED")
        batch = session.scalar(
            sa.select(PricingImportBatchRecord)
            .where(
                PricingImportBatchRecord.tenant_id == context.tenant_id,
                PricingImportBatchRecord.case_id == command.case_id,
                PricingImportBatchRecord.id == command.batch_id,
            )
            .with_for_update()
        )
        if batch is None:
            raise CommandExecutionError("IMPORT_NOT_FOUND_OR_FORBIDDEN")
        latest_transition = session.scalar(
            sa.select(PricingImportTransitionRecord)
            .where(
                PricingImportTransitionRecord.tenant_id == context.tenant_id,
                PricingImportTransitionRecord.batch_id == batch.id,
            )
            .order_by(PricingImportTransitionRecord.version.desc())
            .limit(1)
        )
        current_state = latest_transition.to_state if latest_transition else batch.state
        current_version = (
            latest_transition.version if latest_transition else batch.aggregate_revision
        )
        if current_state != "PREVIEWED":
            raise CommandExecutionError("IMPORT_ALREADY_COMMITTED")
        if current_version != command.expected_batch_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        if batch.error_count or batch.valid_row_count != batch.row_count:
            raise CommandExecutionError("IMPORT_HAS_ERRORS")

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
            raise CommandExecutionError("FINANCIAL_REPORT_NOT_FOUND_OR_FORBIDDEN")
        if snapshot.state != "DRAFT":
            raise CommandExecutionError("FINANCIAL_REPORT_NOT_DRAFT")
        if snapshot.aggregate_revision != command.expected_report_revision:
            raise CommandExecutionError("VERSION_CONFLICT")

        rows = tuple(
            session.scalars(
                sa.select(PricingImportRowRecord)
                .where(
                    PricingImportRowRecord.tenant_id == context.tenant_id,
                    PricingImportRowRecord.batch_id == batch.id,
                )
                .order_by(PricingImportRowRecord.row_number)
            ).all()
        )
        if len(rows) != batch.valid_row_count or any(row.error_codes_json for row in rows):
            raise CommandExecutionError("IMPORT_ROWS_INVALID")
        total_minor = 0
        for row in rows:
            if row.designation is None or row.quantity_decimal is None or row.total_minor is None:
                raise CommandExecutionError("IMPORT_ROWS_INVALID")
            total_minor += row.total_minor
            session.add(
                FinancialReportLineRecord(
                    id=uuid4(),
                    tenant_id=context.tenant_id,
                    snapshot_id=snapshot.id,
                    category="SALES",
                    label=row.designation,
                    quantity_decimal=row.quantity_decimal,
                    unit=row.unit or "U",
                    amount_minor=row.total_minor,
                )
            )
        snapshot.sales_total_minor += total_minor
        snapshot.aggregate_revision += 1
        snapshot.calculated_at = context.received_at
        transition = PricingImportTransitionRecord(
            id=uuid4(),
            tenant_id=context.tenant_id,
            batch_id=batch.id,
            from_state="PREVIEWED",
            to_state="COMMITTED",
            version=current_version + 1,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )
        session.add(transition)
        return HandlerOutcome(
            result_code="PRICING_IMPORT_COMMITTED",
            aggregate_refs=(
                {
                    "aggregate_type": "FinancialReportSnapshot",
                    "aggregate_id": str(snapshot.id),
                    "aggregate_revision": snapshot.aggregate_revision,
                },
                {
                    "aggregate_type": "PricingImportBatch",
                    "aggregate_id": str(batch.id),
                    "aggregate_revision": transition.version,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="FinancialReportSnapshot",
                    aggregate_id=snapshot.id,
                    aggregate_revision=snapshot.aggregate_revision,
                    event_type="PricingImportCommitted",
                    payload={
                        "case_id": str(command.case_id),
                        "batch_id": str(batch.id),
                        "line_count": len(rows),
                        "resulting_revision": snapshot.aggregate_revision,
                    },
                ),
            ),
        )


def pricing_import_handlers() -> dict[str, CommitPricingImportHandler]:
    """Return the closed dispatcher registry for pricing import commands."""

    return {"CommitPricingImport": CommitPricingImportHandler()}

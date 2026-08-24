"""Patron-only publication of immutable financial snapshots.

The service authorizes the financial perimeter before resolving any snapshot.
The handler performs the locked DRAFT -> PUBLISHED mutation and records its
append-only publication act in the same dispatcher transaction.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.dce.application.commands import PublishFinancialReportCommand
from app.modules.pricing.infrastructure.models import (
    FinancialReportPublicationRecord,
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


class PatronFinancialReportPublicationService:
    """Authorize a patron before dispatching an immutable publication command."""

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

    def publish(
        self,
        *,
        actor: ActorContext,
        command: PublishFinancialReportCommand,
        now: datetime,
    ) -> DispatchResult:
        # Absolute financial confidentiality: no snapshot resolution before this guard.
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("FINANCIAL_REPORT_PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.FINANCIAL_REPORT_PUBLISH,
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

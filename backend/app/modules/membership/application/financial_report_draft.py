"""Patron-only creation of an empty, revisioned financial report DRAFT."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.commands import CreateFinancialReportDraftCommand
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
from app.platform.security.models import FinancialReportSnapshotRecord


class PatronFinancialReportDraftCreationService:
    """Authorize a patron before any financial Case or snapshot resolution."""

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

    def create(
        self,
        *,
        actor: ActorContext,
        command: CreateFinancialReportDraftCommand,
        now: datetime,
    ) -> DispatchResult:
        # Absolute financial confidentiality: do not resolve the Case before this guard.
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("FINANCIAL_REPORT_PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.FINANCIAL_REPORT_CREATE,
                resource=AuthorizationResource(
                    resource_type="CASE_FINANCIAL_REPORT",
                    resource_id=command.case_id,
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
                sa.select(CaseRecord.id).where(
                    CaseRecord.tenant_id == actor.tenant_id,
                    CaseRecord.id == command.case_id,
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

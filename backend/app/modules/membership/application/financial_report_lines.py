from __future__ import annotations

from datetime import datetime

from app.modules.dce.application.commands import AddFinancialReportLineCommand
from app.modules.membership.application.financial_report_lines_handler import (
    AddFinancialReportLineHandler,
    financial_report_line_handlers,
)
from app.modules.membership.application.queries import FinancialReportSnapshotExistenceReader
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, DispatchResult
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


class PatronFinancialReportLineService:
    """Authorize a patron before resolving or mutating a financial snapshot."""

    def __init__(
        self,
        *,
        reader: FinancialReportSnapshotExistenceReader,
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._reader = reader
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
        if not self._reader.exists(
            tenant_id=actor.tenant_id,
            case_id=command.case_id,
            report_id=command.report_id,
        ):
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


__all__ = [
    "AddFinancialReportLineHandler",
    "PatronFinancialReportLineService",
    "financial_report_line_handlers",
]

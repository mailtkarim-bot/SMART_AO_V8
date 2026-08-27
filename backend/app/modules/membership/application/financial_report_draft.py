"""Patron-only creation of an empty, revisioned financial report DRAFT."""

from __future__ import annotations

from datetime import datetime

from app.modules.dce.application.commands import CreateFinancialReportDraftCommand
from app.modules.membership.application.financial_report_draft_handler import (
    CreateFinancialReportDraftHandler,
)
from app.modules.membership.application.queries import FinancialDraftCaseReader
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, DispatchResult
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


class PatronFinancialReportDraftCreationService:
    """Authorize a patron before any financial Case or snapshot resolution."""

    def __init__(
        self,
        *,
        reader: FinancialDraftCaseReader,
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._reader = reader
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
        if not self._reader.exists(
            tenant_id=actor.tenant_id,
            case_id=command.case_id,
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
    "CreateFinancialReportDraftHandler",
    "PatronFinancialReportDraftCreationService",
]

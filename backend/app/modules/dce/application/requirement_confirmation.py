"""SEC-01 guarded human confirmation facade for immutable DCE requirements."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.commands import RecordDceRequirementConfirmationCommand
from app.modules.dce.infrastructure.models.dce_requirements import DceRequirementRecord
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, DispatchResult
from app.platform.security.audit import (
    AuditEventType,
    AuditOutcome,
    AuditSeverity,
    SecurityAuditEntry,
    SecurityAuditWriter,
)
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.context import ActorContext, ActorKind, DataClassification


class RequirementCaseScopeError(ValueError):
    """The DCE requirement cannot safely be bound to exactly one active Case."""


class DceRequirementConfirmationService:
    """Resolve Case scope server-side, authorize, then dispatch one human confirmation."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
        audit_writer: SecurityAuditWriter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._policy = policy
        self._audit_writer = audit_writer or SecurityAuditWriter()

    def confirm(
        self,
        *,
        actor: ActorContext,
        command: RecordDceRequirementConfirmationCommand,
        now: datetime,
    ) -> DispatchResult:
        if actor.actor_kind is ActorKind.SYSTEM:
            self._record_manual_denial(
                actor=actor,
                command=command,
                case_id=None,
                now=now,
                reason_code="DCE_REQUIREMENT_HUMAN_ACTOR_REQUIRED",
            )
            raise PermissionError("DCE_REQUIREMENT_HUMAN_ACTOR_REQUIRED")
        try:
            case_id = self._resolve_unique_requirement_case_id(
                tenant_id=actor.tenant_id,
                requirement_id=command.requirement_id,
            )
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                self._record_manual_denial(
                    actor=actor,
                    command=command,
                    case_id=None,
                    now=now,
                    reason_code="NOT_FOUND_OR_FORBIDDEN",
                )
            raise
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action="dce.requirement.confirm",
                resource=AuthorizationResource(
                    resource_type="DCE_REQUIREMENT",
                    resource_id=command.requirement_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)
        if command.outcome == "NOT_APPLICABLE" and actor.actor_kind is ActorKind.COLLABORATEUR:
            self._record_manual_denial(
                actor=actor,
                command=command,
                case_id=case_id,
                now=now,
                reason_code="DCE_REQUIREMENT_PATRON_REQUIRED",
            )
            raise PermissionError("DCE_REQUIREMENT_PATRON_REQUIRED")
        return self._dispatcher.dispatch(
            command=command,
            context=CommandContext(
                tenant_id=actor.tenant_id,
                actor_id=actor.actor_id,
                actor_kind=actor.actor_kind.value,
                received_at=now,
                identity_id=actor.identity_id,
                session_id=actor.session_id,
                case_id=case_id,
                correlation_id=actor.correlation_id,
            ),
        )

    def _record_manual_denial(
        self,
        *,
        actor: ActorContext,
        command: RecordDceRequirementConfirmationCommand,
        case_id: UUID | None,
        now: datetime,
        reason_code: str,
    ) -> None:
        with self._session_factory.begin() as session:
            self._audit_writer.record(
                session=session,
                entry=SecurityAuditEntry(
                    occurred_at=now,
                    tenant_id=actor.tenant_id,
                    actor_id=actor.actor_id,
                    identity_id=actor.identity_id,
                    session_id=actor.session_id,
                    actor_kind=actor.actor_kind.value,
                    auth_strength=None,
                    event_type=AuditEventType.AUTHZ_DENIED,
                    outcome=AuditOutcome.DENIED,
                    severity=AuditSeverity.WARNING,
                    action="dce.requirement.confirm",
                    resource_type="DCE_REQUIREMENT",
                    resource_id=command.requirement_id,
                    case_id=case_id,
                    correlation_id=command.correlation_id,
                    command_id=command.command_id,
                    request_id=None,
                    source_ip_hash=None,
                    user_agent_family=None,
                    reason_code=reason_code,
                    metadata={"channel": "service"},
                ),
            )

    def _resolve_unique_requirement_case_id(
        self,
        *,
        tenant_id: UUID,
        requirement_id: UUID,
    ) -> UUID:
        with self._session_factory() as session:
            dce_version_id = session.scalar(
                sa.select(DceRequirementRecord.dce_version_id).where(
                    DceRequirementRecord.tenant_id == tenant_id,
                    DceRequirementRecord.id == requirement_id,
                )
            )
            if dce_version_id is None:
                raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
            case_ids = list(
                session.scalars(
                    sa.select(CaseRecord.id)
                    .where(
                        CaseRecord.tenant_id == tenant_id,
                        CaseRecord.applicable_dce_version_id == dce_version_id,
                        CaseRecord.lifecycle == "ACTIVE",
                    )
                    .order_by(CaseRecord.id)
                    .limit(2)
                )
            )
        if len(case_ids) != 1:
            raise RequirementCaseScopeError("DCE_REQUIREMENT_CASE_SCOPE_AMBIGUOUS")
        return case_ids[0]

"""CASE-ASSIGNMENT-HISTORY-01 service with ReBAC authorization and denial audit."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.modules.membership.application.queries import AssignmentHistoryLookup
from app.modules.membership.infrastructure.assignment_history_reader import (
    SqlAlchemyAssignmentHistoryReader,
)
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
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


class AssignmentHistoryService:
    """Resolve an owned assignment, authorize its Case scope, then return a closed history."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        policy: AuthorizationPolicyPort,
        audit_writer: SecurityAuditWriter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._policy = policy
        self._audit_writer = audit_writer or SecurityAuditWriter()

    def get(
        self,
        *,
        actor: ActorContext,
        assignment_id: UUID,
        now: datetime,
        limit: int,
    ) -> AssignmentHistoryLookup:
        if actor.actor_kind is not ActorKind.COLLABORATEUR:
            self._record_manual_denial(
                actor=actor,
                assignment_id=assignment_id,
                now=now,
                reason_code="ASSIGNMENT_COLLABORATOR_REQUIRED",
            )
            raise PermissionError("ASSIGNMENT_COLLABORATOR_REQUIRED")
        if actor.membership_id is None:
            self._record_manual_denial(
                actor=actor,
                assignment_id=assignment_id,
                now=now,
                reason_code="ASSIGNMENT_MEMBERSHIP_REQUIRED",
            )
            raise PermissionError("ASSIGNMENT_MEMBERSHIP_REQUIRED")

        with self._session_factory() as session:
            lookup = SqlAlchemyAssignmentHistoryReader(session).get(
                tenant_id=actor.tenant_id,
                membership_id=actor.membership_id,
                assignment_id=assignment_id,
                limit=limit,
            )
        if lookup is None:
            self._record_manual_denial(
                actor=actor,
                assignment_id=assignment_id,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")

        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.ASSIGNMENT_HISTORY_READ,
                resource=AuthorizationResource(
                    resource_type="CASE_ASSIGNMENT_HISTORY",
                    resource_id=lookup.assignment_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=lookup.case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)
        return lookup

    def _record_manual_denial(
        self,
        *,
        actor: ActorContext,
        assignment_id: UUID,
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
                    action=Capability.ASSIGNMENT_HISTORY_READ,
                    resource_type="CASE_ASSIGNMENT_HISTORY",
                    resource_id=assignment_id,
                    case_id=None,
                    correlation_id=actor.correlation_id,
                    command_id=None,
                    request_id=None,
                    source_ip_hash=None,
                    user_agent_family=None,
                    reason_code=reason_code,
                    metadata={"channel": "service"},
                ),
            )

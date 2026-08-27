from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.membership.application.queries import (
    AssignmentManagementCase,
    AssignmentManagementTarget,
)
from app.modules.membership.infrastructure.records import CaseAssignmentRecord
from app.platform.security.audit import (
    AuditEventType,
    AuditOutcome,
    AuditSeverity,
    SecurityAuditEntry,
    SecurityAuditWriter,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext

_ACTION_BY_COMMAND = {
    "AcknowledgeAssignment": Capability.ASSIGNMENT_ACKNOWLEDGE,
    "RequestAssignmentClarification": Capability.ASSIGNMENT_CLARIFY,
    "ReportAssignmentUnavailability": Capability.ASSIGNMENT_UNAVAILABILITY,
}


class SqlAlchemyAssignmentManagementReader:
    """SQLAlchemy adapter for tenant-scoped assignment management lookups."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        audit_writer: SecurityAuditWriter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._audit_writer = audit_writer or SecurityAuditWriter()

    def get_case(self, *, tenant_id: UUID, case_id: UUID) -> AssignmentManagementCase | None:
        with self._session_factory() as session:
            record = session.scalar(
                sa.select(CaseRecord).where(
                    CaseRecord.tenant_id == tenant_id,
                    CaseRecord.id == case_id,
                )
            )
        if record is None:
            return None
        return AssignmentManagementCase(id=record.id, lifecycle=record.lifecycle)

    def get_assignment(
        self, *, tenant_id: UUID, assignment_id: UUID
    ) -> AssignmentManagementTarget | None:
        with self._session_factory() as session:
            record = session.scalar(
                sa.select(CaseAssignmentRecord).where(
                    CaseAssignmentRecord.tenant_id == tenant_id,
                    CaseAssignmentRecord.id == assignment_id,
                )
            )
        if record is None:
            return None
        return AssignmentManagementTarget(
            id=record.id,
            case_id=record.case_id,
            membership_id=record.membership_id,
        )

    def record_denial(
        self, *, actor: ActorContext, command: Any, now: datetime, reason: str
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
                    action=str(_ACTION_BY_COMMAND[command.command_type]),
                    resource_type="CASE_ASSIGNMENT",
                    resource_id=command.assignment_id,
                    case_id=None,
                    correlation_id=command.correlation_id,
                    command_id=command.command_id,
                    request_id=None,
                    source_ip_hash=None,
                    user_agent_family=None,
                    reason_code=reason,
                    metadata={"channel": "service"},
                ),
            )

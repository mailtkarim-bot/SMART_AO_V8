from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.membership.application.collab_work_task_ports import (
    AssignmentProjection,
    CollaboratorTaskProjection,
    CollaboratorWorkTaskReader,
)
from app.modules.membership.infrastructure.records import (
    CaseAssignmentRecord,
    CollaboratorTaskRecord,
)
from app.platform.security.audit import (
    AuditEventType,
    AuditOutcome,
    AuditSeverity,
    SecurityAuditEntry,
    SecurityAuditWriter,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext


class SqlAlchemyCollaboratorWorkTaskReader(CollaboratorWorkTaskReader):
    """SQLAlchemy adapter for Work Task reads and authorization audit entries."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        audit_writer: SecurityAuditWriter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._audit_writer = audit_writer or SecurityAuditWriter()

    def resolve_task_assignment_id(self, *, tenant_id: UUID, task_id: UUID) -> UUID | None:
        with self._session_factory() as session:
            return session.scalar(
                sa.select(CollaboratorTaskRecord.assignment_id).where(
                    CollaboratorTaskRecord.tenant_id == tenant_id,
                    CollaboratorTaskRecord.id == task_id,
                )
            )

    def resolve_assignment(
        self, *, tenant_id: UUID, membership_id: UUID, assignment_id: UUID
    ) -> AssignmentProjection | None:
        with self._session_factory() as session:
            assignment = session.scalar(
                sa.select(CaseAssignmentRecord).where(
                    CaseAssignmentRecord.tenant_id == tenant_id,
                    CaseAssignmentRecord.membership_id == membership_id,
                    CaseAssignmentRecord.id == assignment_id,
                )
            )
            return (
                AssignmentProjection(id=assignment.id, case_id=assignment.case_id)
                if assignment
                else None
            )

    def resolve_active_assignment_for_case(
        self, *, tenant_id: UUID, membership_id: UUID, case_id: UUID
    ) -> AssignmentProjection | None:
        with self._session_factory() as session:
            assignment = session.scalar(
                sa.select(CaseAssignmentRecord).where(
                    CaseAssignmentRecord.tenant_id == tenant_id,
                    CaseAssignmentRecord.membership_id == membership_id,
                    CaseAssignmentRecord.case_id == case_id,
                    CaseAssignmentRecord.state == "ACTIVE",
                )
            )
            return (
                AssignmentProjection(id=assignment.id, case_id=assignment.case_id)
                if assignment
                else None
            )

    def list_for_case(
        self, *, tenant_id: UUID, case_id: UUID, assignment_id: UUID
    ) -> tuple[CollaboratorTaskProjection, ...]:
        with self._session_factory() as session:
            return tuple(
                CollaboratorTaskProjection(
                    id=task.id,
                    case_id=task.case_id,
                    assignment_id=task.assignment_id,
                    requirement_id=task.requirement_id,
                    task_kind=task.task_kind,
                    title=task.title,
                    objective=task.objective,
                    priority=task.priority,
                    state=task.state,
                    due_at=task.due_at,
                    aggregate_revision=task.aggregate_revision,
                )
                for task in session.scalars(
                    sa.select(CollaboratorTaskRecord)
                    .where(
                        CollaboratorTaskRecord.tenant_id == tenant_id,
                        CollaboratorTaskRecord.assignment_id == assignment_id,
                        CollaboratorTaskRecord.case_id == case_id,
                    )
                    .order_by(CollaboratorTaskRecord.created_at, CollaboratorTaskRecord.id)
                ).all()
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
                    action=str(Capability.WORK_TASK_WRITE),
                    resource_type="COLLABORATOR_TASK",
                    resource_id=getattr(command, "task_id", None),
                    case_id=getattr(command, "case_id", None),
                    correlation_id=command.correlation_id,
                    command_id=command.command_id,
                    request_id=None,
                    source_ip_hash=None,
                    user_agent_family=None,
                    reason_code=reason,
                    metadata={"channel": "service"},
                ),
            )

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.membership.application.collab_info_blockers_ports import (
    AssignmentProjection,
    CollaboratorInfoBlockerReader,
    InformationRequestProjection,
    InformationResponseProjection,
    TaskBlockerProjection,
    TaskProjection,
)
from app.modules.membership.infrastructure.records import (
    CaseAssignmentRecord,
    CollaboratorInformationRequestRecord,
    CollaboratorInformationResponseRecord,
    CollaboratorTaskBlockerRecord,
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


class SqlAlchemyCollaboratorInfoBlockerReader(CollaboratorInfoBlockerReader):
    """SQLAlchemy adapter for collaborator workflow authorization and reads."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        audit_writer: SecurityAuditWriter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._audit_writer = audit_writer or SecurityAuditWriter()

    def resolve_task_id(self, *, tenant_id: UUID, request_id: UUID) -> UUID | None:
        with self._session_factory() as session:
            return session.scalar(
                sa.select(CollaboratorTaskRecord.id)
                .join(
                    CollaboratorInformationRequestRecord,
                    sa.and_(
                        CollaboratorInformationRequestRecord.tenant_id
                        == CollaboratorTaskRecord.tenant_id,
                        CollaboratorInformationRequestRecord.task_id == CollaboratorTaskRecord.id,
                    ),
                )
                .where(
                    CollaboratorInformationRequestRecord.tenant_id == tenant_id,
                    CollaboratorInformationRequestRecord.id == request_id,
                )
            )

    def resolve_assignment(
        self, *, tenant_id: UUID, membership_id: UUID, task_id: UUID
    ) -> AssignmentProjection | None:
        with self._session_factory() as session:
            assignment = session.scalar(
                sa.select(CaseAssignmentRecord)
                .join(
                    CollaboratorTaskRecord,
                    sa.and_(
                        CollaboratorTaskRecord.tenant_id == CaseAssignmentRecord.tenant_id,
                        CollaboratorTaskRecord.assignment_id == CaseAssignmentRecord.id,
                    ),
                )
                .where(
                    CaseAssignmentRecord.tenant_id == tenant_id,
                    CaseAssignmentRecord.membership_id == membership_id,
                    CaseAssignmentRecord.state == "ACTIVE",
                    CollaboratorTaskRecord.id == task_id,
                )
            )
            return AssignmentProjection(case_id=assignment.case_id) if assignment else None

    def read_workflow(
        self, *, tenant_id: UUID, task_id: UUID
    ) -> tuple[
        TaskProjection,
        tuple[InformationRequestProjection, ...],
        tuple[InformationResponseProjection, ...],
        tuple[TaskBlockerProjection, ...],
    ]:
        with self._session_factory() as session:
            task = session.scalar(
                sa.select(CollaboratorTaskRecord).where(
                    CollaboratorTaskRecord.tenant_id == tenant_id,
                    CollaboratorTaskRecord.id == task_id,
                )
            )
            if task is None:
                raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
            requests = tuple(
                InformationRequestProjection(
                    id=request.id,
                    task_id=request.task_id,
                    request_kind=request.request_kind,
                    subject=request.subject,
                    question=request.question,
                    requested_object=request.requested_object,
                    reason=request.reason,
                    priority=request.priority,
                    state=request.state,
                    due_at=request.due_at,
                    aggregate_revision=request.aggregate_revision,
                )
                for request in session.scalars(
                    sa.select(CollaboratorInformationRequestRecord)
                    .where(
                        CollaboratorInformationRequestRecord.tenant_id == tenant_id,
                        CollaboratorInformationRequestRecord.task_id == task_id,
                    )
                    .order_by(
                        CollaboratorInformationRequestRecord.created_at,
                        CollaboratorInformationRequestRecord.id,
                    )
                ).all()
            )
            responses = tuple(
                InformationResponseProjection(
                    id=response.id,
                    request_id=response.request_id,
                    request_revision=response.request_revision,
                    outcome=response.outcome,
                    response_text=response.response_text,
                    source_locator=response.source_locator,
                    created_at=response.created_at,
                )
                for response in session.scalars(
                    sa.select(CollaboratorInformationResponseRecord)
                    .join(
                        CollaboratorInformationRequestRecord,
                        sa.and_(
                            CollaboratorInformationResponseRecord.tenant_id
                            == CollaboratorInformationRequestRecord.tenant_id,
                            CollaboratorInformationResponseRecord.request_id
                            == CollaboratorInformationRequestRecord.id,
                        ),
                    )
                    .where(
                        CollaboratorInformationResponseRecord.tenant_id == tenant_id,
                        CollaboratorInformationRequestRecord.task_id == task_id,
                    )
                    .order_by(
                        CollaboratorInformationResponseRecord.created_at,
                        CollaboratorInformationResponseRecord.id,
                    )
                ).all()
            )
            blockers = tuple(
                TaskBlockerProjection(
                    id=blocker.id,
                    task_id=blocker.task_id,
                    task_revision=blocker.task_revision,
                    blocker_kind=blocker.blocker_kind,
                    description=blocker.description,
                    source_locator=blocker.source_locator,
                    resolution_owner=blocker.resolution_owner,
                    state=blocker.state,
                    resolution_note=blocker.resolution_note,
                    resolved_at=blocker.resolved_at,
                )
                for blocker in session.scalars(
                    sa.select(CollaboratorTaskBlockerRecord)
                    .where(
                        CollaboratorTaskBlockerRecord.tenant_id == tenant_id,
                        CollaboratorTaskBlockerRecord.task_id == task_id,
                    )
                    .order_by(
                        CollaboratorTaskBlockerRecord.created_at,
                        CollaboratorTaskBlockerRecord.id,
                    )
                ).all()
            )
            return (
                TaskProjection(
                    id=task.id, state=task.state, aggregate_revision=task.aggregate_revision
                ),
                requests,
                responses,
                blockers,
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

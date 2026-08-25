from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.infrastructure.models.dce_requirements import DceRequirementRecord
from app.modules.membership.application.collab_work_task_commands import (
    CreateTaskFromRequirementCommand,
)
from app.modules.membership.infrastructure.records import (
    CaseAssignmentRecord,
    CollaboratorTaskRecord,
    CollaboratorTaskResultRecord,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
    DispatchResult,
    HandlerOutcome,
    PendingDomainEvent,
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

_TASK_WRITE_COMMANDS = frozenset(
    {
        "CreateTaskFromRequirement",
        "ClaimTask",
        "RecordTaskResult",
        "CompleteTask",
    }
)


class CollaboratorWorkTaskService:
    """Authorize bounded collaborator task mutations, then dispatch atomically."""

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

    def execute(self, *, actor: ActorContext, command, now: datetime) -> DispatchResult:
        if actor.actor_kind is not ActorKind.COLLABORATEUR:
            self._deny(actor=actor, command=command, now=now, reason="COLLABORATOR_REQUIRED")
            raise PermissionError("COLLABORATOR_REQUIRED")
        if actor.membership_id is None:
            self._deny(actor=actor, command=command, now=now, reason="MEMBERSHIP_REQUIRED")
            raise PermissionError("MEMBERSHIP_REQUIRED")
        candidate_assignment_id = getattr(command, "assignment_id", None)
        assignment_id: UUID | None = (
            candidate_assignment_id if isinstance(candidate_assignment_id, UUID) else None
        )
        if assignment_id is None:
            assignment_id = self._task_assignment_id(
                tenant_id=actor.tenant_id, task_id=command.task_id
            )
        if assignment_id is None:
            self._deny(actor=actor, command=command, now=now, reason="NOT_FOUND_OR_FORBIDDEN")
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        assignment = self._resolve_assignment(
            tenant_id=actor.tenant_id,
            membership_id=actor.membership_id,
            assignment_id=assignment_id,
        )
        if assignment is None:
            self._deny(actor=actor, command=command, now=now, reason="NOT_FOUND_OR_FORBIDDEN")
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        action = Capability.WORK_TASK_WRITE
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=action,
                resource=AuthorizationResource(
                    resource_type="COLLABORATOR_TASK",
                    resource_id=assignment.id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=assignment.case_id,
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
                case_id=assignment.case_id,
                correlation_id=actor.correlation_id,
            ),
        )

    def list_for_case(
        self, *, actor: ActorContext, case_id: UUID, now: datetime
    ) -> tuple[CollaboratorTaskRecord, ...]:
        if actor.actor_kind is not ActorKind.COLLABORATEUR or actor.membership_id is None:
            raise PermissionError("COLLABORATOR_REQUIRED")
        assignment = self._assignment_for_case(
            tenant_id=actor.tenant_id,
            membership_id=actor.membership_id,
            case_id=case_id,
        )
        if assignment is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.WORK_TASK_READ,
                resource=AuthorizationResource(
                    resource_type="COLLABORATOR_TASKS",
                    resource_id=assignment.id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)
        with self._session_factory() as session:
            return tuple(
                session.scalars(
                    sa.select(CollaboratorTaskRecord)
                    .where(
                        CollaboratorTaskRecord.tenant_id == actor.tenant_id,
                        CollaboratorTaskRecord.assignment_id == assignment.id,
                        CollaboratorTaskRecord.case_id == case_id,
                    )
                    .order_by(CollaboratorTaskRecord.created_at, CollaboratorTaskRecord.id)
                ).all()
            )

    def _assignment_for_case(
        self, *, tenant_id: UUID, membership_id: UUID, case_id: UUID
    ) -> CaseAssignmentRecord | None:
        with self._session_factory() as session:
            return session.scalar(
                sa.select(CaseAssignmentRecord).where(
                    CaseAssignmentRecord.tenant_id == tenant_id,
                    CaseAssignmentRecord.membership_id == membership_id,
                    CaseAssignmentRecord.case_id == case_id,
                    CaseAssignmentRecord.state == "ACTIVE",
                )
            )

    def _resolve_assignment(self, *, tenant_id: UUID, membership_id: UUID, assignment_id: UUID):
        with self._session_factory() as session:
            return session.scalar(
                sa.select(CaseAssignmentRecord).where(
                    CaseAssignmentRecord.tenant_id == tenant_id,
                    CaseAssignmentRecord.membership_id == membership_id,
                    CaseAssignmentRecord.id == assignment_id,
                )
            )

    def _task_assignment_id(self, *, tenant_id: UUID, task_id: UUID) -> UUID | None:
        with self._session_factory() as session:
            return session.scalar(
                sa.select(CollaboratorTaskRecord.assignment_id).where(
                    CollaboratorTaskRecord.tenant_id == tenant_id,
                    CollaboratorTaskRecord.id == task_id,
                )
            )

    def _deny(self, *, actor: ActorContext, command, now: datetime, reason: str) -> None:
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


class CollaboratorWorkTaskHandler:
    """Own task transitions and append-only result writes."""

    def execute(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        if context.actor_kind != ActorKind.COLLABORATEUR.value or context.membership_id is None:
            raise CommandExecutionError("COLLABORATOR_REQUIRED")
        if command.command_type == "CreateTaskFromRequirement":
            return self._create(session=session, command=command, context=context)
        task = session.scalar(
            sa.select(CollaboratorTaskRecord)
            .where(
                CollaboratorTaskRecord.tenant_id == context.tenant_id,
                CollaboratorTaskRecord.id == command.task_id,
            )
            .with_for_update()
        )
        if task is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        self._ensure_assignment(session=session, task=task, context=context)
        if task.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        if command.command_type == "ClaimTask":
            return self._claim(task=task, context=context)
        if command.command_type == "RecordTaskResult":
            return self._record_result(session=session, task=task, command=command, context=context)
        if command.command_type == "CompleteTask":
            return self._complete(session=session, task=task, context=context)
        raise CommandExecutionError(f"unsupported task command: {command.command_type}")

    @staticmethod
    def _ensure_assignment(
        *, session: Session, task: CollaboratorTaskRecord, context: CommandContext
    ) -> None:
        assignment = session.scalar(
            sa.select(CaseAssignmentRecord).where(
                CaseAssignmentRecord.tenant_id == context.tenant_id,
                CaseAssignmentRecord.id == task.assignment_id,
            )
        )
        if assignment is None or assignment.membership_id != context.membership_id:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if assignment.state != "ACTIVE":
            raise CommandExecutionError("ASSIGNMENT_INACTIVE")
        if assignment.starts_at > context.received_at or (
            assignment.ends_at is not None and assignment.ends_at <= context.received_at
        ):
            raise CommandExecutionError("ASSIGNMENT_INACTIVE")
        if Capability.WORK_TASK_WRITE.value not in assignment.scope_actions_json:
            raise CommandExecutionError("ASSIGNMENT_SCOPE_FORBIDDEN")
        if (
            DataClassification.INTERNAL_OPERATIONAL.value
            not in assignment.scope_classifications_json
        ):
            raise CommandExecutionError("ASSIGNMENT_CLASSIFICATION_FORBIDDEN")
        if context.case_id is not None and context.case_id != task.case_id:
            raise CommandExecutionError("CASE_CONTEXT_MISMATCH")

    @staticmethod
    def _create(
        *, session: Session, command: CreateTaskFromRequirementCommand, context: CommandContext
    ) -> HandlerOutcome:
        assignment = session.scalar(
            sa.select(CaseAssignmentRecord)
            .where(
                CaseAssignmentRecord.tenant_id == context.tenant_id,
                CaseAssignmentRecord.id == command.assignment_id,
            )
            .with_for_update()
        )
        if assignment is None or assignment.membership_id != context.membership_id:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if assignment.state != "ACTIVE":
            raise CommandExecutionError("ASSIGNMENT_INACTIVE")
        if assignment.case_id != command.case_id:
            raise CommandExecutionError("CASE_CONTEXT_MISMATCH")
        if Capability.WORK_TASK_WRITE.value not in assignment.scope_actions_json:
            raise CommandExecutionError("ASSIGNMENT_SCOPE_FORBIDDEN")
        case = session.scalar(
            sa.select(CaseRecord).where(
                CaseRecord.tenant_id == context.tenant_id,
                CaseRecord.id == command.case_id,
            )
        )
        requirement = session.scalar(
            sa.select(DceRequirementRecord).where(
                DceRequirementRecord.tenant_id == context.tenant_id,
                DceRequirementRecord.id == command.requirement_id,
            )
        )
        if case is None or case.lifecycle == "ARCHIVED" or requirement is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if case.applicable_dce_version_id != requirement.dce_version_id:
            raise CommandExecutionError("STALE_CONTEXT")
        functional_key = f"{command.requirement_id}:{command.task_kind}:{assignment.id}"
        existing = session.scalar(
            sa.select(CollaboratorTaskRecord).where(
                CollaboratorTaskRecord.tenant_id == context.tenant_id,
                CollaboratorTaskRecord.assignment_id == assignment.id,
                CollaboratorTaskRecord.functional_key == functional_key,
            )
        )
        if existing is not None:
            return CollaboratorWorkTaskHandler._outcome(task=existing, event=None)
        task = CollaboratorTaskRecord(
            id=command.task_id,
            tenant_id=context.tenant_id,
            case_id=assignment.case_id,
            assignment_id=assignment.id,
            requirement_id=requirement.id,
            task_kind=command.task_kind,
            title=command.title,
            objective=command.objective,
            priority="NORMAL",
            state="READY",
            functional_key=functional_key,
            due_at=command.due_at,
            aggregate_revision=0,
        )
        session.add(task)
        return CollaboratorWorkTaskHandler._outcome(
            task=task,
            event=PendingDomainEvent(
                aggregate_type="CollaboratorTask",
                aggregate_id=task.id,
                aggregate_revision=0,
                event_type="TaskCreatedFromRequirement",
                payload={
                    "task_id": str(task.id),
                    "case_id": str(task.case_id),
                    "assignment_id": str(task.assignment_id),
                    "requirement_id": str(task.requirement_id),
                    "state": task.state,
                },
            ),
        )

    @staticmethod
    def _claim(*, task: CollaboratorTaskRecord, context: CommandContext) -> HandlerOutcome:
        if task.state != "READY":
            raise CommandExecutionError("TASK_NOT_CLAIMABLE")
        task.state = "IN_PROGRESS"
        task.aggregate_revision += 1
        task.claimed_at = context.received_at
        return CollaboratorWorkTaskHandler._outcome(
            task=task,
            event=PendingDomainEvent(
                aggregate_type="CollaboratorTask",
                aggregate_id=task.id,
                aggregate_revision=task.aggregate_revision,
                event_type="TaskClaimed",
                payload={"task_id": str(task.id), "state": task.state},
            ),
        )

    @staticmethod
    def _record_result(*, session: Session, task, command, context) -> HandlerOutcome:
        if task.state not in {"IN_PROGRESS", "READY"}:
            raise CommandExecutionError("TASK_NOT_ACTIVE")
        revision = task.aggregate_revision + 1
        session.add(
            CollaboratorTaskResultRecord(
                id=uuid4(),
                tenant_id=context.tenant_id,
                task_id=task.id,
                task_revision=revision,
                outcome=command.outcome,
                result_text=command.result_text,
                source_locator=command.source_locator,
                actor_id=context.actor_id,
                membership_id=context.membership_id,
                command_id=command.command_id,
                correlation_id=command.correlation_id,
            )
        )
        task.aggregate_revision = revision
        return CollaboratorWorkTaskHandler._outcome(
            task=task,
            event=PendingDomainEvent(
                aggregate_type="CollaboratorTask",
                aggregate_id=task.id,
                aggregate_revision=revision,
                event_type="TaskResultRecorded",
                payload={"task_id": str(task.id), "state": task.state, "result_revision": revision},
            ),
            result_code="TASK_UPDATED",
        )

    @staticmethod
    def _complete(*, session: Session, task, context: CommandContext) -> HandlerOutcome:
        if task.state not in {"IN_PROGRESS", "READY"}:
            raise CommandExecutionError("TASK_NOT_COMPLETABLE")
        result = session.scalar(
            sa.select(CollaboratorTaskResultRecord.id).where(
                CollaboratorTaskResultRecord.tenant_id == context.tenant_id,
                CollaboratorTaskResultRecord.task_id == task.id,
            )
        )
        if result is None:
            raise CommandExecutionError("EVIDENCE_OF_COMPLETION_REQUIRED")
        task.state = "COMPLETED"
        task.aggregate_revision += 1
        task.completed_at = context.received_at
        return CollaboratorWorkTaskHandler._outcome(
            task=task,
            event=PendingDomainEvent(
                aggregate_type="CollaboratorTask",
                aggregate_id=task.id,
                aggregate_revision=task.aggregate_revision,
                event_type="TaskCompleted",
                payload={"task_id": str(task.id), "state": task.state},
            ),
        )

    @staticmethod
    def _outcome(
        *,
        task: CollaboratorTaskRecord,
        event: PendingDomainEvent | None,
        result_code: str | None = None,
    ) -> HandlerOutcome:
        return HandlerOutcome(
            result_code=result_code
            or {
                "READY": "TASK_CREATED",
                "IN_PROGRESS": "TASK_CLAIMED",
                "COMPLETED": "TASK_COMPLETED",
            }.get(task.state, "TASK_UPDATED"),
            aggregate_refs=(
                {
                    "aggregate_type": "CollaboratorTask",
                    "aggregate_id": str(task.id),
                    "aggregate_revision": task.aggregate_revision,
                },
            ),
            events=(event,) if event is not None else (),
        )


def collaborator_work_task_handlers() -> dict[str, CollaboratorWorkTaskHandler]:
    handler = CollaboratorWorkTaskHandler()
    return {command_type: handler for command_type in _TASK_WRITE_COMMANDS}

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

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
    CommandExecutionError,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorKind, DataClassification

_TASK_WRITE_COMMANDS = frozenset(
    {
        "CreateTaskFromRequirement",
        "ClaimTask",
        "RecordTaskResult",
        "CompleteTask",
    }
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

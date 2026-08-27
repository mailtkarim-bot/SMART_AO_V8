from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.membership.application.collab_info_blockers_commands import (
    CreateInformationRequestCommand,
)
from app.modules.membership.infrastructure.records import (
    CaseAssignmentRecord,
    CollaboratorInformationRequestRecord,
    CollaboratorInformationResponseRecord,
    CollaboratorTaskBlockerRecord,
    CollaboratorTaskRecord,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandExecutionError,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorKind, DataClassification


class CollaboratorInfoBlockerHandler:
    """Own information request revisions and task blocker transitions."""

    def execute(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        if context.actor_kind != ActorKind.COLLABORATEUR.value or context.membership_id is None:
            raise CommandExecutionError("COLLABORATOR_REQUIRED")
        if command.command_type == "CreateInformationRequest":
            return self._create_request(session=session, command=command, context=context)
        if command.command_type == "RecordInformationRequestResponse":
            return self._record_response(session=session, command=command, context=context)
        task = self._task(session=session, task_id=command.task_id, context=context)
        self._ensure_assignment(session=session, task=task, context=context)
        if task.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        if command.command_type == "DeclareTaskBlocker":
            return self._declare_blocker(
                session=session, task=task, command=command, context=context
            )
        if command.command_type == "ResolveTaskBlocker":
            return self._resolve_blocker(
                session=session, task=task, command=command, context=context
            )
        raise CommandExecutionError(f"unsupported info/blocker command: {command.command_type}")

    @staticmethod
    def _task(
        *, session: Session, task_id: UUID, context: CommandContext
    ) -> CollaboratorTaskRecord:
        task = session.scalar(
            sa.select(CollaboratorTaskRecord)
            .where(
                CollaboratorTaskRecord.tenant_id == context.tenant_id,
                CollaboratorTaskRecord.id == task_id,
            )
            .with_for_update()
        )
        if task is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        return task

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
    def _create_request(
        *, session: Session, command: CreateInformationRequestCommand, context: CommandContext
    ) -> HandlerOutcome:
        task = CollaboratorInfoBlockerHandler._task(
            session=session, task_id=command.task_id, context=context
        )
        CollaboratorInfoBlockerHandler._ensure_assignment(
            session=session, task=task, context=context
        )
        if task.aggregate_revision != command.expected_task_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        if task.state in {"COMPLETED", "ABANDONED"}:
            raise CommandExecutionError("TASK_NOT_ACTIVE")
        functional_key = f"{command.request_kind}:{command.requested_object.strip().lower()}"
        existing = session.scalar(
            sa.select(CollaboratorInformationRequestRecord).where(
                CollaboratorInformationRequestRecord.tenant_id == context.tenant_id,
                CollaboratorInformationRequestRecord.task_id == task.id,
                CollaboratorInformationRequestRecord.functional_key == functional_key,
            )
        )
        if existing is not None:
            return CollaboratorInfoBlockerHandler._request_outcome(request=existing, event=None)
        request = CollaboratorInformationRequestRecord(
            id=command.request_id,
            tenant_id=context.tenant_id,
            task_id=task.id,
            request_kind=command.request_kind,
            subject=command.subject,
            question=command.question,
            requested_object=command.requested_object,
            reason=command.reason,
            priority=command.priority,
            state="OPEN",
            functional_key=functional_key,
            due_at=command.due_at,
            aggregate_revision=0,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            correlation_id=command.correlation_id,
        )
        session.add(request)
        return CollaboratorInfoBlockerHandler._request_outcome(
            request=request,
            event=PendingDomainEvent(
                aggregate_type="InformationRequest",
                aggregate_id=request.id,
                aggregate_revision=0,
                event_type="InformationRequestCreated",
                payload={
                    "request_id": str(request.id),
                    "task_id": str(task.id),
                    "state": request.state,
                    "request_kind": request.request_kind,
                },
            ),
        )

    @staticmethod
    def _record_response(*, session: Session, command, context: CommandContext) -> HandlerOutcome:
        request = session.scalar(
            sa.select(CollaboratorInformationRequestRecord)
            .where(
                CollaboratorInformationRequestRecord.tenant_id == context.tenant_id,
                CollaboratorInformationRequestRecord.id == command.request_id,
            )
            .with_for_update()
        )
        if request is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        task = CollaboratorInfoBlockerHandler._task(
            session=session, task_id=request.task_id, context=context
        )
        CollaboratorInfoBlockerHandler._ensure_assignment(
            session=session, task=task, context=context
        )
        if request.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        if request.state != "OPEN":
            raise CommandExecutionError("REQUEST_NOT_OPEN")
        revision = request.aggregate_revision + 1
        session.add(
            CollaboratorInformationResponseRecord(
                id=command.command_id,
                tenant_id=context.tenant_id,
                request_id=request.id,
                request_revision=revision,
                outcome=command.outcome,
                response_text=command.response_text,
                source_locator=command.source_locator,
                actor_id=context.actor_id,
                membership_id=context.membership_id,
                command_id=command.command_id,
                correlation_id=command.correlation_id,
            )
        )
        request.state = "ANSWERED"
        request.aggregate_revision = revision
        return CollaboratorInfoBlockerHandler._request_outcome(
            request=request,
            event=PendingDomainEvent(
                aggregate_type="InformationRequest",
                aggregate_id=request.id,
                aggregate_revision=revision,
                event_type="RequestResponseReceived",
                payload={
                    "request_id": str(request.id),
                    "task_id": str(request.task_id),
                    "state": request.state,
                    "outcome": command.outcome,
                },
            ),
        )

    @staticmethod
    def _declare_blocker(*, session: Session, task, command, context) -> HandlerOutcome:
        if task.state in {"COMPLETED", "ABANDONED"}:
            raise CommandExecutionError("TASK_TERMINAL")
        blocker = CollaboratorTaskBlockerRecord(
            id=command.blocker_id,
            tenant_id=context.tenant_id,
            task_id=task.id,
            task_revision=task.aggregate_revision + 1,
            blocker_kind=command.blocker_kind,
            description=command.description,
            source_locator=command.source_locator,
            resolution_owner=command.resolution_owner,
            state="OPEN",
            resolution_note=None,
            resolved_at=None,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            correlation_id=command.correlation_id,
        )
        session.add(blocker)
        task.state = "BLOCKED"
        task.aggregate_revision += 1
        return CollaboratorInfoBlockerHandler._task_outcome(
            task=task,
            event=PendingDomainEvent(
                aggregate_type="CollaboratorTask",
                aggregate_id=task.id,
                aggregate_revision=task.aggregate_revision,
                event_type="TaskBlockerDeclared",
                payload={
                    "task_id": str(task.id),
                    "blocker_id": str(blocker.id),
                    "state": task.state,
                    "blocker_kind": blocker.blocker_kind,
                },
            ),
            result_code="TASK_BLOCKED",
        )

    @staticmethod
    def _resolve_blocker(*, session: Session, task, command, context) -> HandlerOutcome:
        blocker = session.scalar(
            sa.select(CollaboratorTaskBlockerRecord)
            .where(
                CollaboratorTaskBlockerRecord.tenant_id == context.tenant_id,
                CollaboratorTaskBlockerRecord.id == command.blocker_id,
                CollaboratorTaskBlockerRecord.task_id == task.id,
            )
            .with_for_update()
        )
        if blocker is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if blocker.state != "OPEN":
            raise CommandExecutionError("BLOCKER_ALREADY_RESOLVED")
        revision = task.aggregate_revision + 1
        blocker.state = "RESOLVED"
        blocker.task_revision = revision
        blocker.resolution_note = command.resolution_note
        blocker.resolved_at = context.received_at
        task.state = "IN_PROGRESS"
        task.aggregate_revision = revision
        return CollaboratorInfoBlockerHandler._task_outcome(
            task=task,
            event=PendingDomainEvent(
                aggregate_type="CollaboratorTask",
                aggregate_id=task.id,
                aggregate_revision=revision,
                event_type="TaskBlockerResolved",
                payload={
                    "task_id": str(task.id),
                    "blocker_id": str(blocker.id),
                    "state": task.state,
                },
            ),
            result_code="TASK_UNBLOCKED",
        )

    @staticmethod
    def _request_outcome(*, request, event: PendingDomainEvent | None) -> HandlerOutcome:
        return HandlerOutcome(
            result_code="INFORMATION_REQUEST_ANSWERED"
            if request.state == "ANSWERED"
            else "INFORMATION_REQUEST_CREATED",
            aggregate_refs=(
                {
                    "aggregate_type": "InformationRequest",
                    "aggregate_id": str(request.id),
                    "aggregate_revision": request.aggregate_revision,
                },
            ),
            events=(event,) if event is not None else (),
        )

    @staticmethod
    def _task_outcome(*, task, event: PendingDomainEvent, result_code: str) -> HandlerOutcome:
        return HandlerOutcome(
            result_code=result_code,
            aggregate_refs=(
                {
                    "aggregate_type": "CollaboratorTask",
                    "aggregate_id": str(task.id),
                    "aggregate_revision": task.aggregate_revision,
                },
            ),
            events=(event,),
        )

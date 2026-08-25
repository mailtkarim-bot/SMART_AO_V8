from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

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

_INFO_BLOCKER_COMMANDS = frozenset(
    {
        "CreateInformationRequest",
        "RecordInformationRequestResponse",
        "DeclareTaskBlocker",
        "ResolveTaskBlocker",
    }
)


class CollaboratorInfoBlockerService:
    """Authorize info/blocker commands against the active task assignment."""

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
        if actor.actor_kind is not ActorKind.COLLABORATEUR or actor.membership_id is None:
            self._deny(actor=actor, command=command, now=now, reason="COLLABORATOR_REQUIRED")
            raise PermissionError("COLLABORATOR_REQUIRED")
        task_id = self._resolve_task_id(tenant_id=actor.tenant_id, command=command)
        if task_id is None:
            self._deny(actor=actor, command=command, now=now, reason="NOT_FOUND_OR_FORBIDDEN")
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        assignment = self._resolve_assignment(
            tenant_id=actor.tenant_id,
            membership_id=actor.membership_id,
            task_id=task_id,
        )
        if assignment is None:
            self._deny(actor=actor, command=command, now=now, reason="NOT_FOUND_OR_FORBIDDEN")
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.WORK_TASK_WRITE,
                resource=AuthorizationResource(
                    resource_type="COLLABORATOR_TASK",
                    resource_id=task_id,
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

    def read_workflow(
        self, *, actor: ActorContext, task_id: UUID, now: datetime
    ) -> tuple[
        CollaboratorTaskRecord,
        tuple[CollaboratorInformationRequestRecord, ...],
        tuple[CollaboratorInformationResponseRecord, ...],
        tuple[CollaboratorTaskBlockerRecord, ...],
    ]:
        if actor.actor_kind is not ActorKind.COLLABORATEUR or actor.membership_id is None:
            raise PermissionError("COLLABORATOR_REQUIRED")
        assignment = self._resolve_assignment(
            tenant_id=actor.tenant_id,
            membership_id=actor.membership_id,
            task_id=task_id,
        )
        if assignment is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.WORK_TASK_READ,
                resource=AuthorizationResource(
                    resource_type="COLLABORATOR_TASK_WORKFLOW",
                    resource_id=task_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=assignment.case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)
        with self._session_factory() as session:
            task = session.scalar(
                sa.select(CollaboratorTaskRecord).where(
                    CollaboratorTaskRecord.tenant_id == actor.tenant_id,
                    CollaboratorTaskRecord.id == task_id,
                )
            )
            if task is None:
                raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
            requests = tuple(
                session.scalars(
                    sa.select(CollaboratorInformationRequestRecord)
                    .where(
                        CollaboratorInformationRequestRecord.tenant_id == actor.tenant_id,
                        CollaboratorInformationRequestRecord.task_id == task_id,
                    )
                    .order_by(
                        CollaboratorInformationRequestRecord.created_at,
                        CollaboratorInformationRequestRecord.id,
                    )
                ).all()
            )
            responses = tuple(
                session.scalars(
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
                        CollaboratorInformationResponseRecord.tenant_id == actor.tenant_id,
                        CollaboratorInformationRequestRecord.task_id == task_id,
                    )
                    .order_by(
                        CollaboratorInformationResponseRecord.created_at,
                        CollaboratorInformationResponseRecord.id,
                    )
                ).all()
            )
            blockers = tuple(
                session.scalars(
                    sa.select(CollaboratorTaskBlockerRecord)
                    .where(
                        CollaboratorTaskBlockerRecord.tenant_id == actor.tenant_id,
                        CollaboratorTaskBlockerRecord.task_id == task_id,
                    )
                    .order_by(
                        CollaboratorTaskBlockerRecord.created_at,
                        CollaboratorTaskBlockerRecord.id,
                    )
                ).all()
            )
            return task, requests, responses, blockers

    def _resolve_task_id(self, *, tenant_id: UUID, command) -> UUID | None:
        if hasattr(command, "task_id"):
            return command.task_id
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
                    CollaboratorInformationRequestRecord.id == command.request_id,
                )
            )

    def _resolve_assignment(
        self, *, tenant_id: UUID, membership_id: UUID, task_id: UUID
    ) -> CaseAssignmentRecord | None:
        with self._session_factory() as session:
            return session.scalar(
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


def collaborator_info_blocker_handlers() -> dict[str, CollaboratorInfoBlockerHandler]:
    handler = CollaboratorInfoBlockerHandler()
    return {command_type: handler for command_type in _INFO_BLOCKER_COMMANDS}

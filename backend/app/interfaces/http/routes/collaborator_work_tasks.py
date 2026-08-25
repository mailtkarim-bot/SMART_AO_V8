from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.membership.application.collab_work_task import CollaboratorWorkTaskService
from app.modules.membership.application.collab_work_task_commands import (
    ClaimTaskCommand,
    CompleteTaskCommand,
    CreateTaskFromRequirementCommand,
    RecordTaskResultCommand,
)
from app.modules.membership.public.collab_work_task_contracts import (
    ClaimCollaboratorTaskRequest,
    CollaboratorTaskCommandResponse,
    CollaboratorTaskListResponse,
    CollaboratorTaskProjection,
    CompleteCollaboratorTaskRequest,
    CreateCollaboratorTaskRequest,
    RecordCollaboratorTaskResultRequest,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)


def build_collaborator_work_task_router(
    *,
    service: CollaboratorWorkTaskService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/collaborator", tags=["collaborator-work"])

    @router.get(
        "/cases/{case_id}/tasks",
        response_model=CollaboratorTaskListResponse,
    )
    def list_tasks(
        case_id: UUID,
        authorization: str | None = Header(default=None),
    ) -> CollaboratorTaskListResponse:
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            tasks = service.list_for_case(
                actor=actor,
                case_id=case_id,
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="NOT_FOUND_OR_FORBIDDEN",
                ) from error
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
            ) from error
        return CollaboratorTaskListResponse(
            case_id=case_id,
            tasks=[
                CollaboratorTaskProjection(
                    task_id=task.id,
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
                for task in tasks
            ],
        )

    @router.post(
        "/cases/{case_id}/assignments/{assignment_id}/tasks",
        status_code=status.HTTP_201_CREATED,
        response_model=CollaboratorTaskCommandResponse,
    )
    def create_task(
        case_id: UUID,
        assignment_id: UUID,
        request: CreateCollaboratorTaskRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service=service,
            actor=actor,
            command=CreateTaskFromRequirementCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                task_id=request.command_id,
                assignment_id=assignment_id,
                case_id=case_id,
                requirement_id=request.requirement_id,
                task_kind=request.task_kind,
                title=request.title,
                objective=request.objective,
                due_at=request.due_at,
            ),
        )

    @router.post(
        "/tasks/{task_id}/claim",
        status_code=status.HTTP_201_CREATED,
        response_model=CollaboratorTaskCommandResponse,
    )
    def claim_task(
        task_id: UUID,
        request: ClaimCollaboratorTaskRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service=service,
            actor=actor,
            command=ClaimTaskCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                task_id=task_id,
                expected_revision=request.expected_revision,
            ),
        )

    @router.post(
        "/tasks/{task_id}/results",
        status_code=status.HTTP_201_CREATED,
        response_model=CollaboratorTaskCommandResponse,
    )
    def record_result(
        task_id: UUID,
        request: RecordCollaboratorTaskResultRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service=service,
            actor=actor,
            command=RecordTaskResultCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                task_id=task_id,
                expected_revision=request.expected_revision,
                result_text=request.result_text,
                source_locator=request.source_locator,
                outcome=request.outcome,
            ),
        )

    @router.post(
        "/tasks/{task_id}/complete",
        status_code=status.HTTP_201_CREATED,
        response_model=CollaboratorTaskCommandResponse,
    )
    def complete_task(
        task_id: UUID,
        request: CompleteCollaboratorTaskRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service=service,
            actor=actor,
            command=CompleteTaskCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                task_id=task_id,
                expected_revision=request.expected_revision,
            ),
        )

    return router


def _dispatch(*, service, actor, command):
    try:
        result = service.execute(actor=actor, command=command, now=datetime.now(tz=UTC))
    except PermissionError as error:
        if str(error) == "NOT_FOUND_OR_FORBIDDEN":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="NOT_FOUND_OR_FORBIDDEN"
            ) from error
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN") from error
    except IdempotencyKeyReusedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="IDEMPOTENCY_KEY_REUSED"
        ) from error
    except CommandInProgressError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="COMMAND_IN_PROGRESS"
        ) from error
    except CommandExecutionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error

    response = CollaboratorTaskCommandResponse(
        command_id=result.command_id,
        idempotency_key=result.idempotency_key,
        result_code=result.result_code,
        aggregate_refs=list(result.aggregate_refs),
        event_ids=list(result.event_ids),
        replayed=result.replayed,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED,
        content=response.model_dump(mode="json"),
    )

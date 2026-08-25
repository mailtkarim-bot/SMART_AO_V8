from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.membership.application.collab_info_blockers import CollaboratorInfoBlockerService
from app.modules.membership.application.collab_info_blockers_commands import (
    CreateInformationRequestCommand,
    DeclareTaskBlockerCommand,
    RecordInformationRequestResponseCommand,
    ResolveTaskBlockerCommand,
)
from app.modules.membership.public.collab_info_blockers_contracts import (
    CollaboratorTaskWorkflowResponse,
    CreateInformationRequestHttpRequest,
    DeclareTaskBlockerHttpRequest,
    InfoBlockerAggregateReference,
    InfoBlockerCommandResponse,
    InformationRequestProjection,
    InformationResponseProjection,
    RecordInformationResponseHttpRequest,
    ResolveTaskBlockerHttpRequest,
    TaskBlockerProjection,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)


def build_collaborator_info_blocker_router(
    *,
    service: CollaboratorInfoBlockerService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/collaborator", tags=["collaborator-workflow"])

    @router.get(
        "/tasks/{task_id}/workflow",
        response_model=CollaboratorTaskWorkflowResponse,
    )
    def read_workflow(
        task_id: UUID,
        authorization: str | None = Header(default=None),
    ) -> CollaboratorTaskWorkflowResponse:
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            task, requests, responses, blockers = service.read_workflow(
                actor=actor, task_id=task_id, now=datetime.now(tz=UTC)
            )
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="NOT_FOUND_OR_FORBIDDEN"
                ) from error
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
            ) from error
        responses_by_request: dict[UUID, list[InformationResponseProjection]] = {}
        for response in responses:
            responses_by_request.setdefault(response.request_id, []).append(
                InformationResponseProjection(
                    response_id=response.id,
                    request_revision=response.request_revision,
                    outcome=response.outcome,
                    response_text=response.response_text,
                    source_locator=response.source_locator,
                    created_at=response.created_at,
                )
            )
        return CollaboratorTaskWorkflowResponse(
            task_id=task.id,
            state=task.state,
            aggregate_revision=task.aggregate_revision,
            information_requests=[
                InformationRequestProjection(
                    request_id=request.id,
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
                    responses=responses_by_request.get(request.id, []),
                )
                for request in requests
            ],
            blockers=[
                TaskBlockerProjection(
                    blocker_id=blocker.id,
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
                for blocker in blockers
            ],
        )

    @router.post(
        "/tasks/{task_id}/information-requests",
        status_code=status.HTTP_201_CREATED,
        response_model=InfoBlockerCommandResponse,
    )
    def create_request(
        task_id: UUID,
        request: CreateInformationRequestHttpRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service=service,
            actor=actor,
            command=CreateInformationRequestCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                request_id=request.command_id,
                task_id=task_id,
                expected_task_revision=request.expected_task_revision,
                request_kind=request.request_kind,
                subject=request.subject,
                question=request.question,
                requested_object=request.requested_object,
                reason=request.reason,
                priority=request.priority,
                due_at=request.due_at,
            ),
        )

    @router.post(
        "/information-requests/{request_id}/responses",
        status_code=status.HTTP_201_CREATED,
        response_model=InfoBlockerCommandResponse,
    )
    def record_response(
        request_id: UUID,
        request: RecordInformationResponseHttpRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service=service,
            actor=actor,
            command=RecordInformationRequestResponseCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                request_id=request_id,
                expected_revision=request.expected_revision,
                response_text=request.response_text,
                source_locator=request.source_locator,
                outcome=request.outcome,
            ),
        )

    @router.post(
        "/tasks/{task_id}/blockers",
        status_code=status.HTTP_201_CREATED,
        response_model=InfoBlockerCommandResponse,
    )
    def declare_blocker(
        task_id: UUID,
        request: DeclareTaskBlockerHttpRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service=service,
            actor=actor,
            command=DeclareTaskBlockerCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                task_id=task_id,
                expected_revision=request.expected_revision,
                blocker_id=request.command_id,
                blocker_kind=request.blocker_kind,
                description=request.description,
                source_locator=request.source_locator,
                resolution_owner=request.resolution_owner,
            ),
        )

    @router.post(
        "/tasks/{task_id}/blockers/{blocker_id}/resolve",
        status_code=status.HTTP_201_CREATED,
        response_model=InfoBlockerCommandResponse,
    )
    def resolve_blocker(
        task_id: UUID,
        blocker_id: UUID,
        request: ResolveTaskBlockerHttpRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service=service,
            actor=actor,
            command=ResolveTaskBlockerCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                task_id=task_id,
                blocker_id=blocker_id,
                expected_revision=request.expected_revision,
                resolution_note=request.resolution_note,
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

    response = InfoBlockerCommandResponse(
        command_id=result.command_id,
        idempotency_key=result.idempotency_key,
        result_code=result.result_code,
        aggregate_refs=[InfoBlockerAggregateReference(**ref) for ref in result.aggregate_refs],
        event_ids=list(result.event_ids),
        replayed=result.replayed,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED,
        content=response.model_dump(mode="json"),
    )

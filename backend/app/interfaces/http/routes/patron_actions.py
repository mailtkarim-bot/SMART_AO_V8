from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.aggregate_refs import require_aggregate_revision
from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.patron_action.application.commands import CreatePatronActionCommand
from app.modules.patron_action.application.service import PatronActionService
from app.modules.patron_action.application.transition_commands import TransitionPatronActionCommand
from app.modules.patron_action.application.transition_service import PatronActionTransitionService
from app.modules.patron_action.public.contracts import (
    CreatePatronActionRequest,
    PatronActionCommandResponse,
    PatronActionProjectionResponse,
    PatronActionQueueResponse,
    PatronActionTransitionResponse,
    TransitionPatronActionRequest,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)


def build_patron_action_router(
    *,
    service: PatronActionService,
    transition_service: PatronActionTransitionService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron", tags=["patron-actions"])

    @router.get("/actions", response_model=PatronActionQueueResponse)
    def list_actions(authorization: str | None = Header(default=None)):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            items = service.list_open(actor=actor, now=datetime.now(tz=UTC))
        except PermissionError as error:
            if str(error) == "PATRON_REQUIRED":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
                ) from error
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
            ) from error
        projections = [PatronActionProjectionResponse(**asdict(item)) for item in items]
        return PatronActionQueueResponse(items=projections, open_count=len(projections))

    @router.post(
        "/actions/{action_id}/transitions",
        status_code=status.HTTP_201_CREATED,
        response_model=PatronActionTransitionResponse,
    )
    def transition_action(
        action_id: UUID,
        request: TransitionPatronActionRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            result = transition_service.execute(
                actor=actor,
                command=TransitionPatronActionCommand(
                    command_id=request.command_id,
                    idempotency_key=request.idempotency_key,
                    correlation_id=request.correlation_id,
                    transition_id=request.transition_id,
                    action_id=action_id,
                    expected_revision=request.expected_revision,
                    target_state=request.target_state,
                    reason_code=request.reason_code,
                ),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
            ) from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="IDEMPOTENCY_CONFLICT"
            ) from error
        except CommandExecutionError as error:
            detail = str(error)
            code = (
                status.HTTP_409_CONFLICT
                if detail in {"VERSION_CONFLICT", "ACTION_ALREADY_CLOSED"}
                else status.HTTP_422_UNPROCESSABLE_CONTENT
            )
            raise HTTPException(status_code=code, detail=detail) from error
        response = PatronActionTransitionResponse(
            command_id=result.command_id,
            idempotency_key=result.idempotency_key,
            result_code=result.result_code,
            aggregate_id=UUID(str(result.aggregate_refs[0]["aggregate_id"])),
            aggregate_revision=require_aggregate_revision(
                result.aggregate_refs[0]["aggregate_revision"]
            ),
            event_ids=[UUID(event_id) for event_id in result.event_ids],
            replayed=result.replayed,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED,
            content=response.model_dump(mode="json"),
        )

    @router.post(
        "/actions",
        status_code=status.HTTP_201_CREATED,
        response_model=PatronActionCommandResponse,
    )
    def create_action(
        request: CreatePatronActionRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            result = service.execute(
                actor=actor,
                command=CreatePatronActionCommand(
                    command_id=request.command_id,
                    idempotency_key=request.idempotency_key,
                    correlation_id=request.correlation_id,
                    action_id=request.action_id,
                    case_id=request.case_id,
                    functional_key=request.functional_key,
                    action_type=request.action_type,
                    severity=request.severity,
                    title=request.title,
                    why_now=request.why_now,
                    impact=request.impact,
                    recommended_action=request.recommended_action,
                    due_at=request.due_at,
                    source_refs=request.source_refs,
                ),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            detail = "PATRON_REQUIRED" if str(error) == "PATRON_REQUIRED" else "FORBIDDEN"
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail) from error
        except IdempotencyKeyReusedError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="IDEMPOTENCY_KEY_REUSED"
            ) from error
        except CommandInProgressError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="COMMAND_IN_PROGRESS"
            ) from error
        except CommandExecutionError as error:
            detail = str(error)
            code = (
                status.HTTP_409_CONFLICT
                if detail == "PATRON_ACTION_ALREADY_EXISTS"
                else status.HTTP_422_UNPROCESSABLE_CONTENT
            )
            raise HTTPException(status_code=code, detail=detail) from error
        response = PatronActionCommandResponse(
            command_id=result.command_id,
            idempotency_key=result.idempotency_key,
            result_code=result.result_code,
            aggregate_id=UUID(str(result.aggregate_refs[0]["aggregate_id"])),
            aggregate_revision=require_aggregate_revision(
                result.aggregate_refs[0]["aggregate_revision"]
            ),
            event_ids=[UUID(event_id) for event_id in result.event_ids],
            replayed=result.replayed,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED,
            content=response.model_dump(mode="json"),
        )

    return router

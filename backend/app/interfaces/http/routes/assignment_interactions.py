"""Authenticated HTTP façade for collaborator Assignment interactions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.dce.public.contracts import (
    AcknowledgeAssignmentRequest,
    AssignmentCommandResponse,
    ReportAssignmentUnavailabilityRequest,
    RequestAssignmentClarificationRequest,
)
from app.modules.membership.application.assignment import AssignmentInteractionService
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)


def build_assignment_interaction_router(
    *,
    service: AssignmentInteractionService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    """Build the bearer-authenticated, audited Assignment command façade."""

    router = APIRouter(prefix="/api/v1/assignments", tags=["assignments"])

    @router.post(
        "/{assignment_id}/acknowledgement",
        status_code=status.HTTP_201_CREATED,
        response_model=AssignmentCommandResponse,
    )
    def acknowledge_assignment(
        assignment_id: UUID,
        request: AcknowledgeAssignmentRequest,
        authorization: str | None = Header(default=None),
    ) -> AssignmentCommandResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service.acknowledge,
            actor=context,
            command=request.to_command(assignment_id=assignment_id),
            now=datetime.now(tz=UTC),
        )

    @router.post(
        "/{assignment_id}/clarification-requests",
        status_code=status.HTTP_201_CREATED,
        response_model=AssignmentCommandResponse,
    )
    def request_clarification(
        assignment_id: UUID,
        request: RequestAssignmentClarificationRequest,
        authorization: str | None = Header(default=None),
    ) -> AssignmentCommandResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service.clarify,
            actor=context,
            command=request.to_command(assignment_id=assignment_id),
            now=datetime.now(tz=UTC),
        )

    @router.post(
        "/{assignment_id}/unavailability-reports",
        status_code=status.HTTP_201_CREATED,
        response_model=AssignmentCommandResponse,
    )
    def report_unavailability(
        assignment_id: UUID,
        request: ReportAssignmentUnavailabilityRequest,
        authorization: str | None = Header(default=None),
    ) -> AssignmentCommandResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service.report_unavailability,
            actor=context,
            command=request.to_command(assignment_id=assignment_id),
            now=datetime.now(tz=UTC),
        )

    return router


def _dispatch(call, *, actor, command, now):
    try:
        result = call(actor=actor, command=command, now=now)
    except PermissionError as error:
        if str(error) == "NOT_FOUND_OR_FORBIDDEN":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NOT_FOUND_OR_FORBIDDEN",
            ) from error
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="FORBIDDEN",
        ) from error
    except IdempotencyKeyReusedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="IDEMPOTENCY_KEY_REUSED",
        ) from error
    except CommandInProgressError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="COMMAND_IN_PROGRESS",
        ) from error
    except CommandExecutionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="COMMAND_REJECTED",
        ) from error

    response = AssignmentCommandResponse(
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

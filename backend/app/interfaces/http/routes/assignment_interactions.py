"""Authenticated HTTP façade for collaborator Assignment interactions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
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

_ASSIGNMENT_COMMAND_EXTRA_RESPONSES = {
    status.HTTP_200_OK: {
        "description": "Rejeu idempotent de la commande déjà appliquée.",
        "model": AssignmentCommandResponse,
    },
    status.HTTP_401_UNAUTHORIZED: {"description": "Bearer absent, invalide ou expiré."},
    status.HTTP_403_FORBIDDEN: {"description": "Capability ou scope ReBAC insuffisant."},
    status.HTTP_404_NOT_FOUND: {
        "description": "Affectation absente ou hors tenant : réponse volontairement neutre."
    },
    status.HTTP_409_CONFLICT: {
        "description": "Clé d’idempotence réutilisée ou commande encore en cours."
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "description": "Validation de requête ou rejet métier de la commande."
    },
}


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
        responses=_ASSIGNMENT_COMMAND_EXTRA_RESPONSES,
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
        responses=_ASSIGNMENT_COMMAND_EXTRA_RESPONSES,
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
        responses=_ASSIGNMENT_COMMAND_EXTRA_RESPONSES,
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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

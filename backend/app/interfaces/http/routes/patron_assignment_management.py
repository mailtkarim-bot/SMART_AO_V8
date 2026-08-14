"""Bearer-authenticated patron façade for the currently implemented assignment commands."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.dce.public.contracts import (
    AmendPatronAssignmentScopeRequest,
    AssignmentCommandResponse,
    CreatePatronCaseAssignmentRequest,
    ReactivatePatronCaseAssignmentRequest,
    SuspendPatronCaseAssignmentRequest,
)
from app.modules.membership.application.patron_assignment import PatronAssignmentManagementService
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)

_PATRON_ASSIGNMENT_EXTRA_RESPONSES = {
    status.HTTP_200_OK: {
        "description": "Rejeu idempotent de la commande patron déjà appliquée.",
        "model": AssignmentCommandResponse,
    },
    status.HTTP_401_UNAUTHORIZED: {"description": "Bearer absent, invalide ou expiré."},
    status.HTTP_403_FORBIDDEN: {"description": "Capability patron insuffisante."},
    status.HTTP_404_NOT_FOUND: {
        "description": "Affaire ou affectation absente ou hors tenant : réponse neutre."
    },
    status.HTTP_409_CONFLICT: {
        "description": "Clé d’idempotence réutilisée ou conflit de révision détecté."
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "description": "Validation de requête ou invariant métier refusé."
    },
}


def build_patron_assignment_management_router(
    *,
    service: PatronAssignmentManagementService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    """Expose only the patron commands implemented in the application layer."""

    router = APIRouter(prefix="/api/v1/patron", tags=["patron-assignments"])

    @router.post(
        "/cases/{case_id}/assignments",
        status_code=status.HTTP_201_CREATED,
        response_model=AssignmentCommandResponse,
        responses=_PATRON_ASSIGNMENT_EXTRA_RESPONSES,
    )
    def create_case_assignment(
        case_id: UUID,
        request: CreatePatronCaseAssignmentRequest,
        authorization: str | None = Header(default=None),
    ) -> AssignmentCommandResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service.create,
            actor=context,
            command=request.to_command(case_id=case_id),
            now=datetime.now(tz=UTC),
        )

    @router.post(
        "/assignments/{assignment_id}/scope-amendments",
        status_code=status.HTTP_201_CREATED,
        response_model=AssignmentCommandResponse,
        responses=_PATRON_ASSIGNMENT_EXTRA_RESPONSES,
    )
    def amend_case_assignment_scope(
        assignment_id: UUID,
        request: AmendPatronAssignmentScopeRequest,
        authorization: str | None = Header(default=None),
    ) -> AssignmentCommandResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service.amend_scope,
            actor=context,
            command=request.to_command(assignment_id=assignment_id),
            now=datetime.now(tz=UTC),
        )

    @router.post(
        "/assignments/{assignment_id}/suspensions",
        status_code=status.HTTP_201_CREATED,
        response_model=AssignmentCommandResponse,
        responses=_PATRON_ASSIGNMENT_EXTRA_RESPONSES,
    )
    def suspend_case_assignment(
        assignment_id: UUID,
        request: SuspendPatronCaseAssignmentRequest,
        authorization: str | None = Header(default=None),
    ) -> AssignmentCommandResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service.suspend,
            actor=context,
            command=request.to_command(assignment_id=assignment_id),
            now=datetime.now(tz=UTC),
        )

    @router.post(
        "/assignments/{assignment_id}/reactivations",
        status_code=status.HTTP_201_CREATED,
        response_model=AssignmentCommandResponse,
        responses=_PATRON_ASSIGNMENT_EXTRA_RESPONSES,
    )
    def reactivate_case_assignment(
        assignment_id: UUID,
        request: ReactivatePatronCaseAssignmentRequest,
        authorization: str | None = Header(default=None),
    ) -> AssignmentCommandResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service.reactivate,
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN") from error
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
        if str(error) == "VERSION_CONFLICT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="VERSION_CONFLICT",
            ) from error
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

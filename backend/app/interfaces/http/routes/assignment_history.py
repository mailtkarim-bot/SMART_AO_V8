"""Authenticated HTTP route for a collaborator’s closed Assignment history."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.membership.application.assignment_history import AssignmentHistoryService
from app.modules.membership.public.contracts import (
    AssignmentHistoryItemResponse,
    AssignmentHistoryResponse,
)

_ASSIGNMENT_HISTORY_ERROR_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Bearer absent, invalide ou expiré."},
    status.HTTP_403_FORBIDDEN: {"description": "Capability ou scope ReBAC insuffisant."},
    status.HTTP_404_NOT_FOUND: {
        "description": "Affectation absente ou hors tenant : réponse volontairement neutre."
    },
}


def build_assignment_history_router(
    *,
    service: AssignmentHistoryService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    """Build the Case-scoped, collaborator-only Assignment history read route."""

    router = APIRouter(prefix="/api/v1/assignments", tags=["assignments"])

    @router.get(
        "/{assignment_id}/history",
        response_model=AssignmentHistoryResponse,
        responses=_ASSIGNMENT_HISTORY_ERROR_RESPONSES,
    )
    def get_assignment_history(
        assignment_id: UUID,
        limit: int = Query(default=100, ge=1, le=200),
        authorization: str | None = Header(default=None),
    ) -> AssignmentHistoryResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            lookup = service.get(
                actor=context,
                assignment_id=assignment_id,
                now=datetime.now(tz=UTC),
                limit=limit,
            )
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

        return AssignmentHistoryResponse(
            assignment_id=lookup.assignment_id,
            case_id=lookup.case_id,
            case_lifecycle=lookup.case_lifecycle,
            items=[AssignmentHistoryItemResponse(**asdict(item)) for item in lookup.items],
        )

    return router

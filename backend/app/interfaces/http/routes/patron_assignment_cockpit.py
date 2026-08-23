"""Bearer-authenticated, read-only patron cockpit for assignment authority facts."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.membership.application.patron_assignment_cockpit import (
    PatronAssignmentCockpitService,
)
from app.modules.membership.public.contracts import (
    PatronAssignmentCockpitItemResponse,
    PatronAssignmentCockpitListResponse,
    PatronAssignmentInteractionItemResponse,
    PatronAssignmentInteractionsResponse,
    PatronAssignmentJournalItemResponse,
    PatronAssignmentJournalResponse,
)

PatronAssignmentState = Literal["ACTIVE", "SUSPENDED", "ENDED", "EXPIRED"]
PatronAssignmentInteractionKind = Literal[
    "ACKNOWLEDGEMENT",
    "CLARIFICATION_REQUEST",
    "UNAVAILABILITY_REPORT",
]

_PATRON_ASSIGNMENT_COCKPIT_ERROR_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Bearer absent, invalide ou expiré."},
    status.HTTP_403_FORBIDDEN: {"description": "Capability patron insuffisante."},
    status.HTTP_404_NOT_FOUND: {
        "description": "Affectation absente ou hors tenant : réponse neutre."
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "description": "Paramètre de lecture invalide ou hors borne."
    },
}


def build_patron_assignment_cockpit_router(
    *,
    service: PatronAssignmentCockpitService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    """Build the patron-only closed reads for assignments and authority journal."""

    router = APIRouter(prefix="/api/v1/patron", tags=["patron-assignments"])

    @router.get(
        "/assignments",
        response_model=PatronAssignmentCockpitListResponse,
        responses=_PATRON_ASSIGNMENT_COCKPIT_ERROR_RESPONSES,
    )
    def list_patron_assignments(
        case_id: Annotated[UUID | None, Query()] = None,
        state: Annotated[PatronAssignmentState | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
        authorization: str | None = Header(default=None),
    ) -> PatronAssignmentCockpitListResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            items = service.list(
                actor=context,
                case_id=case_id,
                state=state,
                limit=limit,
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="FORBIDDEN",
            ) from error
        return PatronAssignmentCockpitListResponse(
            items=[PatronAssignmentCockpitItemResponse(**asdict(item)) for item in items]
        )

    @router.get(
        "/assignments/{assignment_id}/journal",
        response_model=PatronAssignmentJournalResponse,
        responses=_PATRON_ASSIGNMENT_COCKPIT_ERROR_RESPONSES,
    )
    def get_patron_assignment_journal(
        assignment_id: UUID,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
        authorization: str | None = Header(default=None),
    ) -> PatronAssignmentJournalResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            lookup = service.get_journal(
                actor=context,
                assignment_id=assignment_id,
                limit=limit,
                now=datetime.now(tz=UTC),
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
        return PatronAssignmentJournalResponse(
            assignment=PatronAssignmentCockpitItemResponse(**asdict(lookup.assignment)),
            items=[PatronAssignmentJournalItemResponse(**asdict(item)) for item in lookup.items],
        )

    @router.get(
        "/assignments/{assignment_id}/interactions",
        response_model=PatronAssignmentInteractionsResponse,
        responses=_PATRON_ASSIGNMENT_COCKPIT_ERROR_RESPONSES,
    )
    def get_patron_assignment_interactions(
        assignment_id: UUID,
        kind: Annotated[PatronAssignmentInteractionKind | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
        authorization: str | None = Header(default=None),
    ) -> PatronAssignmentInteractionsResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            lookup = service.get_interactions(
                actor=context,
                assignment_id=assignment_id,
                kind=kind,
                limit=limit,
                now=datetime.now(tz=UTC),
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
        return PatronAssignmentInteractionsResponse(
            assignment_id=lookup.assignment_id,
            case_id=lookup.case_id,
            case_lifecycle=lookup.case_lifecycle,
            items=[
                PatronAssignmentInteractionItemResponse(**asdict(item))
                for item in lookup.items
            ],
        )

    return router

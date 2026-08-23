from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.opportunity.application.patron_watch_profile import PatronWatchProfileService
from app.modules.opportunity.public.watch_profile_contracts import (
    AddWatchProfileVersionRequest,
    CreateWatchProfileRequest,
    WatchProfileListResponse,
    WatchProfileReceiptResponse,
    WatchProfileResponse,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)


def _receipt(result) -> WatchProfileReceiptResponse:
    return WatchProfileReceiptResponse(
        command_id=result.command_id,
        idempotency_key=result.idempotency_key,
        result_code=result.result_code,
        aggregate_refs=list(result.aggregate_refs),
        event_ids=list(result.event_ids),
        replayed=result.replayed,
    )


def build_patron_opportunity_watch_profile_router(
    *,
    service: PatronWatchProfileService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/patron/opportunity-watch-profiles",
        tags=["patron-opportunity-watch-profiles"],
    )

    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
        response_model=WatchProfileReceiptResponse,
        responses={
            200: {"description": "Rejeu idempotent de la création."},
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Capability réservée au patron."},
            409: {"description": "Conflit d’idempotence ou profil existant."},
            422: {"description": "Invariant du profil refusé."},
        },
    )
    def create_profile(
        request: CreateWatchProfileRequest,
        authorization: str | None = Header(default=None),
    ) -> WatchProfileReceiptResponse:
        context = _resolve_context(
            authorization=authorization, context_resolver=security_runtime.context_resolver
        )
        try:
            result = service.create(
                actor=context,
                command=request.to_command(),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            raise _permission_http_error(error) from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
        except CommandExecutionError as error:
            if str(error) == "OPPORTUNITY_PROFILE_ALREADY_EXISTS":
                raise HTTPException(
                    status_code=409, detail="OPPORTUNITY_PROFILE_ALREADY_EXISTS"
                ) from error
            raise HTTPException(status_code=422, detail="COMMAND_REJECTED") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail="INVALID_PROFILE_CRITERIA") from error
        receipt = _receipt(result)
        return JSONResponse(
            status_code=200 if result.replayed else 201,
            content=receipt.model_dump(mode="json"),
        )

    @router.post(
        "/{profile_id}/versions",
        status_code=status.HTTP_201_CREATED,
        response_model=WatchProfileReceiptResponse,
        responses={
            200: {"description": "Rejeu idempotent du versionnement."},
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Capability réservée au patron."},
            404: {"description": "Profil absent ou hors tenant."},
            409: {"description": "Conflit d’idempotence ou de révision."},
            422: {"description": "Invariant de version refusé."},
        },
    )
    def add_version(
        profile_id: UUID,
        request: AddWatchProfileVersionRequest,
        authorization: str | None = Header(default=None),
    ) -> WatchProfileReceiptResponse:
        context = _resolve_context(
            authorization=authorization, context_resolver=security_runtime.context_resolver
        )
        try:
            result = service.add_version(
                actor=context,
                command=request.to_command(profile_id=profile_id),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            raise _permission_http_error(error) from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
        except CommandExecutionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            if str(error) == "VERSION_CONFLICT":
                raise HTTPException(status_code=409, detail="VERSION_CONFLICT") from error
            if str(error) == "OPPORTUNITY_PROFILE_VERSION_ALREADY_EXISTS":
                raise HTTPException(
                    status_code=409, detail="OPPORTUNITY_PROFILE_VERSION_ALREADY_EXISTS"
                ) from error
            raise HTTPException(status_code=422, detail="COMMAND_REJECTED") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail="INVALID_PROFILE_CRITERIA") from error
        receipt = _receipt(result)
        return JSONResponse(
            status_code=200 if result.replayed else 201,
            content=receipt.model_dump(mode="json"),
        )

    @router.get(
        "",
        response_model=WatchProfileListResponse,
        responses={
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Capability réservée au patron."},
        },
    )
    def read_profiles(
        authorization: str | None = Header(default=None),
    ) -> WatchProfileListResponse:
        context = _resolve_context(
            authorization=authorization, context_resolver=security_runtime.context_resolver
        )
        try:
            profiles = service.read_all(actor=context, now=datetime.now(tz=UTC))
        except PermissionError as error:
            raise _permission_http_error(error) from error
        return WatchProfileListResponse(
            profiles=[WatchProfileResponse.from_projection(profile) for profile in profiles]
        )

    @router.get(
        "/{profile_id}",
        response_model=WatchProfileResponse,
        responses={
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Capability réservée au patron."},
            404: {"description": "Profil absent ou hors tenant."},
        },
    )
    def read_profile(
        profile_id: UUID,
        authorization: str | None = Header(default=None),
    ) -> WatchProfileResponse:
        context = _resolve_context(
            authorization=authorization, context_resolver=security_runtime.context_resolver
        )
        try:
            profile = service.read(actor=context, profile_id=profile_id, now=datetime.now(tz=UTC))
        except PermissionError as error:
            raise _permission_http_error(error) from error
        return WatchProfileResponse.from_projection(profile)

    return router


def _permission_http_error(error: PermissionError) -> HTTPException:
    if str(error) == "NOT_FOUND_OR_FORBIDDEN":
        return HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN")
    return HTTPException(status_code=403, detail="FORBIDDEN")

"""Authenticated DCE-STAGING-01 transport for private staging intents only."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.dce.application.commands import PrepareDceStagingCommand
from app.modules.dce.public.contracts import (
    PrepareDceStagingRequest,
    PrepareDceStagingResponse,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandExecutionError,
    IdempotencyKeyReusedError,
)
from app.platform.security.authenticated_context import UnauthenticatedError
from app.platform.security.authorization import AuthorizationRequest, AuthorizationResource
from app.platform.security.capabilities import Capability
from app.platform.security.context import DataClassification


def build_dce_staging_router(
    *,
    runtime,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    """Build the no-binary staging route defined by DCE-STAGING-01."""

    router = APIRouter(prefix="/api/v1/dce-staged-objects", tags=["dce-staging"])

    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
        response_model=PrepareDceStagingResponse,
    )
    def prepare_dce_staging(
        request: PrepareDceStagingRequest,
        authorization: str | None = Header(default=None),
    ) -> PrepareDceStagingResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        owner_tenant_id = runtime.get_consultation_tenant_id(
            consultation_id=request.consultation_id
        )
        if owner_tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NOT_FOUND_OR_FORBIDDEN",
            )
        decision = security_runtime.policy.authorize(
            context=context,
            request=AuthorizationRequest(
                action=Capability.DCE_PREPARE,
                resource=AuthorizationResource(
                    resource_type="CONSULTATION",
                    resource_id=request.consultation_id,
                    tenant_id=owner_tenant_id,
                    classification=DataClassification.PUBLIC_TENDER,
                ),
                evaluated_at=datetime.now(tz=UTC),
            ),
        )
        if not decision.allowed:
            raise HTTPException(status_code=decision.http_status_code, detail=decision.code)

        storage_object_id = _storage_object_id(
            tenant_id=context.tenant_id,
            actor_id=context.actor_id,
            idempotency_key=request.idempotency_key,
        )
        command = PrepareDceStagingCommand(
            **request.model_dump(),
            storage_object_id=storage_object_id,
        )
        command_context = CommandContext(
            tenant_id=str(context.tenant_id),
            actor_id=str(context.actor_id),
            actor_kind=context.actor_kind.value,
            received_at=datetime.now(tz=UTC),
        )
        try:
            result = runtime.dispatcher.dispatch(command=command, context=command_context)
        except IdempotencyKeyReusedError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="IDEMPOTENCY_KEY_REUSED",
            ) from error
        except CommandExecutionError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="COMMAND_REJECTED",
            ) from error

        response = PrepareDceStagingResponse(
            command_id=result.command_id,
            idempotency_key=result.idempotency_key,
            result_code=result.result_code,
            aggregate_refs=list(result.aggregate_refs),
            event_ids=list(result.event_ids),
            staging={
                "storage_object_id": storage_object_id,
                "state": "AWAITING_UPLOAD",
                "expires_at": request.expires_at,
            },
            replayed=result.replayed,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED,
            content=response.model_dump(mode="json"),
        )

    return router


def _storage_object_id(*, tenant_id: UUID, actor_id: UUID, idempotency_key: UUID) -> UUID:
    """Derive an opaque server identity stable for one tenant-actor idempotent intent."""

    return uuid5(tenant_id, f"{actor_id}:{idempotency_key}")


def _resolve_context(*, authorization: str | None, context_resolver):
    if authorization is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHENTICATED")
    scheme, _, access_token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHENTICATED")
    try:
        return context_resolver.resolve(access_token=access_token)
    except UnauthenticatedError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="UNAUTHENTICATED",
        ) from error

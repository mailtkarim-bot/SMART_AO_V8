"""Authenticated DCE-STAGING-01 transport for private staging intents only."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.interfaces.http.dependencies.auth import resolve_bearer_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.dce.application.commands import PrepareDceStagingCommand
from app.modules.dce.application.upload import (
    DceUploadAlreadyClaimedError,
    DceUploadRejectedError,
)
from app.modules.dce.public.contracts import (
    PrepareDceStagingRequest,
    PrepareDceStagingResponse,
    UploadDceStagedObjectResponse,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandExecutionError,
    IdempotencyKeyReusedError,
)
from app.platform.security.authorization import AuthorizationRequest, AuthorizationResource
from app.platform.security.capabilities import Capability
from app.platform.security.context import DataClassification

IDEMPOTENCY_KEY_HEADER = Header(default=None, alias="Idempotency-Key")


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

    @router.put(
        "/{storage_object_id}/content",
        response_model=UploadDceStagedObjectResponse,
    )
    async def upload_dce_staged_object(
        storage_object_id: UUID,
        request: Request,
        idempotency_key: UUID | None = IDEMPOTENCY_KEY_HEADER,
        authorization: str | None = Header(default=None),
    ) -> UploadDceStagedObjectResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        if idempotency_key is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="IDEMPOTENCY_KEY_REQUIRED",
            )
        target = runtime.get_dce_staged_object_upload_target(
            storage_object_id=storage_object_id
        )
        if target is None:
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
                    resource_id=target.consultation_id,
                    tenant_id=target.tenant_id,
                    classification=DataClassification.PUBLIC_TENDER,
                ),
                evaluated_at=datetime.now(tz=UTC),
            ),
        )
        if not decision.allowed:
            raise HTTPException(status_code=decision.http_status_code, detail=decision.code)
        _reject_non_binary_content_type(content_type=request.headers.get("content-type"))

        try:
            result = await runtime.dce_upload_service.upload(
                tenant_id=context.tenant_id,
                actor_id=context.actor_id,
                actor_kind=context.actor_kind.value,
                storage_object_id=storage_object_id,
                storage_key=target.storage_key,
                expected_byte_size=target.expected_byte_size,
                idempotency_key=idempotency_key,
                stream=request.stream(),
                content_length=_content_length(request.headers.get("content-length")),
            )
        except DceUploadAlreadyClaimedError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="DCE_STAGED_OBJECT_NOT_AWAITING_UPLOAD",
            ) from error
        except DceUploadRejectedError as error:
            raise HTTPException(
                status_code=error.status_code,
                detail="UPLOAD_REJECTED",
            ) from error

        return UploadDceStagedObjectResponse(
            storage_object_id=result.storage_object_id,
            state=result.state,
        )

    return router


def _storage_object_id(*, tenant_id: UUID, actor_id: UUID, idempotency_key: UUID) -> UUID:
    """Derive an opaque server identity stable for one tenant-actor idempotent intent."""

    return uuid5(tenant_id, f"{actor_id}:{idempotency_key}")


def _reject_non_binary_content_type(*, content_type: str | None) -> None:
    if content_type is None:
        return
    normalized = content_type.split(";", maxsplit=1)[0].casefold().strip()
    if normalized in {"application/json", "multipart/form-data"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="BINARY_STREAM_REQUIRED",
        )


def _content_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_CONTENT_LENGTH",
        ) from error
    if parsed < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_CONTENT_LENGTH",
        )
    return parsed


def _resolve_context(*, authorization: str | None, context_resolver):
    return resolve_bearer_context(
        authorization=authorization,
        context_resolver=context_resolver,
    )

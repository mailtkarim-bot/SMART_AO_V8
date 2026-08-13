"""HTTP transport for the first Consultation command and RYOW query."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from app.modules.dce.public.contracts import (
    ConsultationProjectionResponse,
    CreateConsultationRequest,
    CreateConsultationResponse,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandExecutionError,
    IdempotencyKeyReusedError,
)

if TYPE_CHECKING:
    from app.bootstrap.application import AppRuntime

CommandContextResolver = Callable[[], CommandContext]


def build_consultation_router(
    *,
    runtime: AppRuntime,
    command_context_resolver: CommandContextResolver,
) -> APIRouter:
    """Build transport-only routes for the Consultation public contract."""

    router = APIRouter(prefix="/api/v1/consultations", tags=["consultations"])

    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
        response_model=CreateConsultationResponse,
    )
    def create_consultation(request: CreateConsultationRequest) -> CreateConsultationResponse:
        context = command_context_resolver()
        try:
            result = runtime.dispatcher.dispatch(command=request, context=context)
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

        response = CreateConsultationResponse(
            command_id=result.command_id,
            idempotency_key=result.idempotency_key,
            result_code=result.result_code,
            aggregate_refs=list(result.aggregate_refs),
            event_ids=list(result.event_ids),
            projection={"status": "CURRENT"},
            replayed=result.replayed,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED,
            content=response.model_dump(mode="json"),
        )

    @router.get("/{consultation_id}", response_model=ConsultationProjectionResponse)
    def get_consultation(consultation_id: UUID) -> ConsultationProjectionResponse:
        context = command_context_resolver()
        projection = runtime.get_consultation_projection(
            tenant_id=context.tenant_id,
            consultation_id=consultation_id,
        )
        if projection is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NOT_FOUND_OR_FORBIDDEN",
            )
        return ConsultationProjectionResponse(
            id=projection.id,
            buyer_legal_name=projection.buyer_legal_name,
            external_reference=projection.external_reference,
            object_label=projection.object_label,
            location_label=projection.location_label,
            lifecycle=projection.lifecycle,
            freshness=projection.freshness,
            aggregate_revision=projection.aggregate_revision,
            lots=list(projection.lots),
            tranches=list(projection.tranches),
            projection_status=projection.projection_status,
        )

    return router

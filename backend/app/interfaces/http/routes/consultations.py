"""Authenticated HTTP transport for Consultation commands and tenant-scoped projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.dependencies.auth import resolve_bearer_context
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
from app.platform.security.authenticated_context import (
    AuthenticationContextResolver,
)
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, DataClassification


@dataclass(frozen=True, slots=True)
class ConsultationSecurityRuntime:
    """Trusted security dependencies required by every Consultation route."""

    context_resolver: AuthenticationContextResolver
    policy: AuthorizationPolicyPort


def build_consultation_router(
    *,
    runtime,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    """Build Consultation routes that never accept client-provided authorization facts."""

    router = APIRouter(prefix="/api/v1/consultations", tags=["consultations"])

    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
        response_model=CreateConsultationResponse,
    )
    def create_consultation(
        request: CreateConsultationRequest,
        authorization: str | None = Header(default=None),
    ) -> CreateConsultationResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        _authorize(
            context=context,
            policy=security_runtime.policy,
            action=Capability.CONSULTATION_CREATE,
            resource_id=request.consultation_id,
            tenant_id=context.tenant_id,
        )
        command_context = CommandContext(
            tenant_id=str(context.tenant_id),
            actor_id=str(context.actor_id),
            actor_kind=context.actor_kind.value,
            received_at=datetime.now(tz=UTC),
        )
        try:
            result = runtime.dispatcher.dispatch(command=request, context=command_context)
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
    def get_consultation(
        consultation_id: UUID,
        authorization: str | None = Header(default=None),
    ) -> ConsultationProjectionResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        owner_tenant_id = runtime.get_consultation_tenant_id(consultation_id=consultation_id)
        if owner_tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NOT_FOUND_OR_FORBIDDEN",
            )
        _authorize(
            context=context,
            policy=security_runtime.policy,
            action=Capability.CONSULTATION_READ,
            resource_id=consultation_id,
            tenant_id=owner_tenant_id,
        )
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


def _resolve_context(
    *,
    authorization: str | None,
    context_resolver: AuthenticationContextResolver,
) -> ActorContext:
    return resolve_bearer_context(
        authorization=authorization,
        context_resolver=context_resolver,
    )


def _authorize(
    *,
    context: ActorContext,
    policy: AuthorizationPolicyPort,
    action: str,
    resource_id: UUID,
    tenant_id: UUID,
) -> None:
    decision = policy.authorize(
        context=context,
        request=AuthorizationRequest(
            action=action,
            resource=AuthorizationResource(
                resource_type="CONSULTATION",
                resource_id=resource_id,
                tenant_id=tenant_id,
                classification=DataClassification.PUBLIC_TENDER,
            ),
            evaluated_at=datetime.now(tz=UTC),
        ),
    )
    if not decision.allowed:
        raise HTTPException(status_code=decision.http_status_code, detail=decision.code)

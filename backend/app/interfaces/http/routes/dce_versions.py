"""Authenticated DCE-READ-01 HTTP transport for DceVersion metadata only."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.dce.public.contracts import DceVersionMetadataResponse
from app.platform.security.authenticated_context import UnauthenticatedError
from app.platform.security.authorization import AuthorizationRequest, AuthorizationResource
from app.platform.security.capabilities import Capability
from app.platform.security.context import DataClassification


def build_dce_version_router(
    *,
    runtime,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    """Build the metadata-only DceVersion read route defined by DCE-READ-01."""

    router = APIRouter(prefix="/api/v1/dce-versions", tags=["dce-versions"])

    @router.get("/{dce_version_id}", response_model=DceVersionMetadataResponse)
    def get_dce_version(
        dce_version_id: UUID,
        authorization: str | None = Header(default=None),
    ) -> DceVersionMetadataResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        owner_tenant_id = runtime.get_dce_version_tenant_id(dce_version_id=dce_version_id)
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
                    resource_type="DCE_VERSION",
                    resource_id=dce_version_id,
                    tenant_id=owner_tenant_id,
                    classification=DataClassification.PUBLIC_TENDER,
                ),
                evaluated_at=datetime.now(tz=UTC),
            ),
        )
        if not decision.allowed:
            raise HTTPException(status_code=decision.http_status_code, detail=decision.code)
        record = runtime.get_dce_version_metadata(
            tenant_id=context.tenant_id,
            dce_version_id=dce_version_id,
        )
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NOT_FOUND_OR_FORBIDDEN",
            )
        return DceVersionMetadataResponse(
            id=record.id,
            consultation_id=record.consultation_id,
            predecessor_dce_version_id=record.predecessor_dce_version_id,
            source_received_at=record.source_received_at,
            lifecycle=record.lifecycle,
            integrity=record.integrity,
            classification_readiness=record.classification_readiness,
            analysis_readiness=record.analysis_readiness,
            aggregate_revision=record.aggregate_revision,
        )

    return router


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

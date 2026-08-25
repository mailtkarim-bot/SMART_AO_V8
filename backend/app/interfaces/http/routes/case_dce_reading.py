"""SEC-01 guarded HTTP transport for closed Case-scoped DCE reading."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.dce.application.queries import CaseDceReadingAvailability
from app.modules.dce.public.contracts import (
    CaseDceReadingCountersResponse,
    CaseDceReadingDceResponse,
    CaseDceReadingRequirementResponse,
    CaseDceReadingResponse,
)
from app.platform.security.authorization import AuthorizationRequest, AuthorizationResource
from app.platform.security.capabilities import Capability
from app.platform.security.context import DataClassification


def build_case_dce_reading_router(
    *,
    runtime,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    """Build the authenticated closed DCE-reading route for one Case."""

    router = APIRouter(prefix="/api/v1/cases", tags=["cases"])

    @router.get("/{case_id}/dce-reading", response_model=CaseDceReadingResponse)
    def get_case_dce_reading(
        case_id: UUID,
        authorization: str | None = Header(default=None),
    ) -> CaseDceReadingResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        owner_tenant_id = runtime.get_case_tenant_id(case_id=case_id)
        if owner_tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NOT_FOUND_OR_FORBIDDEN",
            )

        decision = security_runtime.policy.authorize(
            context=context,
            request=AuthorizationRequest(
                action=Capability.CASE_DCE_READ,
                resource=AuthorizationResource(
                    resource_type="CASE_DCE_READING",
                    resource_id=case_id,
                    tenant_id=owner_tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=case_id,
                ),
                evaluated_at=datetime.now(tz=UTC),
            ),
        )
        if not decision.allowed:
            if decision.http_status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="NOT_FOUND_OR_FORBIDDEN",
                )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")

        lookup = runtime.get_case_dce_reading(tenant_id=context.tenant_id, case_id=case_id)
        if lookup is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NOT_FOUND_OR_FORBIDDEN",
            )
        if lookup.availability is not CaseDceReadingAvailability.AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="COMMAND_REJECTED",
            )
        if lookup.reading is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="COMMAND_REJECTED",
            )

        reading = lookup.reading
        return CaseDceReadingResponse(
            case_id=lookup.case_id,
            work_label=lookup.work_label,
            case_lifecycle=lookup.case_lifecycle,
            commercial_stage=lookup.commercial_stage,
            dce_freshness=lookup.dce_freshness,
            availability=lookup.availability.value,
            dce=CaseDceReadingDceResponse(
                dce_version_id=reading.dce_version_id,
                lifecycle=reading.lifecycle,
                integrity=reading.integrity,
                classification_readiness=reading.classification_readiness,
                analysis_readiness=reading.analysis_readiness,
                source_received_at=reading.source_received_at,
            ),
            counters=CaseDceReadingCountersResponse(
                total=reading.counters.total,
                pending_human_confirmation=reading.counters.pending_human_confirmation,
                confirmed=reading.counters.confirmed,
                review_required=reading.counters.review_required,
                not_applicable=reading.counters.not_applicable,
            ),
            requirements=[
                CaseDceReadingRequirementResponse(
                    requirement_id=requirement.requirement_id,
                    requirement_type=requirement.requirement_type,
                    directive_signal=requirement.directive_signal,
                    confirmation_outcome=requirement.confirmation_outcome,
                    uncertainty_status=requirement.uncertainty_status,
                    document_family=requirement.document_family,
                    source_locator_label=requirement.source_locator_label,
                )
                for requirement in reading.requirements
            ],
        )

    return router

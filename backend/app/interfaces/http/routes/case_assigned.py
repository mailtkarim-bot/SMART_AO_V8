"""Authenticated, closed collection of Cases visible to the current actor."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Header

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.dce.public.contracts import AssignedCaseResponse
from app.platform.security.authorization import AuthorizationRequest, AuthorizationResource
from app.platform.security.capabilities import Capability
from app.platform.security.context import DataClassification


def build_assigned_case_router(
    *, runtime, security_runtime: ConsultationSecurityRuntime
) -> APIRouter:
    """Build the Case collection on the existing bearer and audited policy path."""

    router = APIRouter(prefix="/api/v1/cases", tags=["cases"])

    @router.get("/assigned", response_model=list[AssignedCaseResponse])
    def list_assigned_cases(
        authorization: str | None = Header(default=None),
    ) -> list[AssignedCaseResponse]:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        candidates = runtime.get_assigned_case_candidates(tenant_id=context.tenant_id)
        visible: list[AssignedCaseResponse] = []
        for candidate in candidates:
            decision = security_runtime.policy.authorize(
                context=context,
                request=AuthorizationRequest(
                    action=Capability.CASE_DCE_READ,
                    resource=AuthorizationResource(
                        resource_type="CASE_DCE_READING",
                        resource_id=candidate.case_id,
                        tenant_id=context.tenant_id,
                        classification=DataClassification.INTERNAL_OPERATIONAL,
                        case_id=candidate.case_id,
                    ),
                    evaluated_at=datetime.now(tz=UTC),
                ),
            )
            if decision.allowed:
                visible.append(
                    AssignedCaseResponse(
                        case_id=candidate.case_id,
                        work_label=candidate.work_label,
                        case_lifecycle=candidate.case_lifecycle,
                        commercial_stage=candidate.commercial_stage,
                        dce_availability=candidate.dce_availability,
                    )
                )
        return visible

    return router

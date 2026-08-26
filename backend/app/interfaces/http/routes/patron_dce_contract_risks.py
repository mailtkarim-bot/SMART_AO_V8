from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.dce.application.contract_risk_read import PatronDceContractRiskReadService
from app.modules.dce.public.contracts import (
    DceContractRiskSignalPageResponse,
    DceContractRiskSignalResponse,
)


def build_patron_dce_contract_risk_router(
    *,
    service: PatronDceContractRiskReadService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron", tags=["patron-dce-contract-risks"])

    @router.get(
        "/cases/{case_id}/dce-contract-risk-signals",
        response_model=DceContractRiskSignalPageResponse,
    )
    def list_contract_risk_signals(
        case_id: UUID,
        limit: int = Query(default=50, ge=1, le=100),
        authorization: str | None = Header(default=None),
    ) -> DceContractRiskSignalPageResponse:
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            items = service.list_for_case(
                actor=actor,
                case_id=case_id,
                limit=limit,
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="FORBIDDEN",
            ) from error
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="INVALID_LIMIT",
            ) from error
        return DceContractRiskSignalPageResponse(
            case_id=case_id,
            items=[
                DceContractRiskSignalResponse(
                    observation_id=item.observation_id,
                    dce_version_id=item.dce_version_id,
                    document_family=item.document_family,
                    requirement_kind=item.requirement_kind,
                    rule_id=item.rule_id,
                    rule_version=item.rule_version,
                    directive=item.directive,
                    fragment_id=item.fragment_id,
                    source_locator_label=item.source_locator_label,
                    start_byte_offset=item.start_byte_offset,
                    end_byte_offset=item.end_byte_offset,
                    verification_status=item.verification_status,
                )
                for item in items
            ],
        )

    return router

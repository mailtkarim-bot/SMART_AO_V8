"""Patron-only closed reads of immutable published financial reports."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response, status

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.membership.application.financial_report import PatronFinancialReportService
from app.modules.membership.public.contracts import (
    PatronFinancialReportLineResponse,
    PatronFinancialReportResponse,
    PatronFinancialReportSummaryResponse,
)


def build_patron_financial_report_router(
    *,
    service: PatronFinancialReportService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron", tags=["patron-financial-reports"])

    @router.get(
        "/cases/{case_id}/financial-reports/{report_id}",
        response_model=PatronFinancialReportResponse,
        responses={
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Accès financier patron insuffisant."},
            404: {"description": "Rapport absent, non publié ou hors tenant."},
            422: {"description": "UUID invalide."},
        },
    )
    def get_financial_report(
        case_id: UUID,
        report_id: UUID,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> PatronFinancialReportResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            report = service.get(
                actor=context,
                case_id=case_id,
                report_id=report_id,
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
        response.headers["Cache-Control"] = "no-store"
        return PatronFinancialReportResponse(
            report_id=report.report_id,
            case_id=report.case_id,
            status="PUBLISHED",
            currency_code=report.currency_code,
            calculated_at=report.calculated_at,
            ruleset_version=report.ruleset_version,
            summary=PatronFinancialReportSummaryResponse(**report.summary),
            lines=[PatronFinancialReportLineResponse(**asdict(line)) for line in report.lines],
        )

    return router

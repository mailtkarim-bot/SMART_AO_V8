"""Patron-only closed reads of immutable published financial reports."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.dce.public.contracts import (
    AddFinancialReportLineRequest,
    CreateFinancialReportDraftRequest,
    FinancialReportDraftCreationResponse,
    FinancialReportLineAdditionResponse,
    FinancialReportPublicationResponse,
    PublishFinancialReportRequest,
)
from app.modules.membership.application.financial_report import PatronFinancialReportService
from app.modules.membership.application.financial_report_draft import (
    PatronFinancialReportDraftCreationService,
)
from app.modules.membership.application.financial_report_publication import (
    PatronFinancialReportPublicationService,
)
from app.modules.membership.public.contracts import (
    PatronFinancialReportDraftResponse,
    PatronFinancialReportLineResponse,
    PatronFinancialReportResponse,
    PatronFinancialReportSummaryResponse,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)


def build_patron_financial_report_router(
    *,
    service: PatronFinancialReportService,
    line_service,
    draft_creation_service: PatronFinancialReportDraftCreationService,
    publication_service: PatronFinancialReportPublicationService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron", tags=["patron-financial-reports"])

    @router.post(
        "/cases/{case_id}/financial-reports/drafts",
        status_code=status.HTTP_201_CREATED,
        response_model=FinancialReportDraftCreationResponse,
        responses={
            200: {"description": "Rejeu idempotent de la création."},
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Création financière réservée au patron."},
            404: {"description": "Affaire absente ou hors tenant."},
            409: {"description": "Conflit d’idempotence."},
            422: {"description": "Invariant de création refusé."},
        },
    )
    def create_financial_report_draft(
        case_id: UUID,
        request: CreateFinancialReportDraftRequest,
        authorization: str | None = Header(default=None),
    ) -> FinancialReportDraftCreationResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            result = draft_creation_service.create(
                actor=context,
                command=request.to_command(case_id=case_id),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
        except CommandExecutionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=422, detail="COMMAND_REJECTED") from error
        receipt = FinancialReportDraftCreationResponse(
            command_id=result.command_id,
            idempotency_key=result.idempotency_key,
            result_code=result.result_code,
            aggregate_refs=list(result.aggregate_refs),
            event_ids=list(result.event_ids),
            replayed=result.replayed,
        )
        return JSONResponse(
            status_code=200 if result.replayed else 201,
            content=receipt.model_dump(mode="json"),
        )

    @router.post(
        "/cases/{case_id}/financial-reports/{report_id}/lines",
        status_code=status.HTTP_201_CREATED,
        response_model=FinancialReportLineAdditionResponse,
        responses={
            200: {"description": "Rejeu idempotent de l’ajout."},
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Écriture financière réservée au patron."},
            404: {"description": "Rapport absent ou hors tenant."},
            409: {"description": "Conflit de révision ou d’idempotence."},
            422: {"description": "Snapshot publié ou invariant de ligne refusé."},
        },
    )
    def add_financial_report_line(
        case_id: UUID,
        report_id: UUID,
        request: AddFinancialReportLineRequest,
        authorization: str | None = Header(default=None),
    ) -> FinancialReportLineAdditionResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            result = line_service.add_line(
                actor=context,
                command=request.to_command(case_id=case_id, report_id=report_id),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
        except CommandExecutionError as error:
            if str(error) == "VERSION_CONFLICT":
                raise HTTPException(status_code=409, detail="VERSION_CONFLICT") from error
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=422, detail="COMMAND_REJECTED") from error
        receipt = FinancialReportLineAdditionResponse(
            command_id=result.command_id,
            idempotency_key=result.idempotency_key,
            result_code=result.result_code,
            aggregate_refs=list(result.aggregate_refs),
            event_ids=list(result.event_ids),
            replayed=result.replayed,
        )
        return JSONResponse(
            status_code=200 if result.replayed else 201,
            content=receipt.model_dump(mode="json"),
        )

    @router.post(
        "/cases/{case_id}/financial-reports/{report_id}/publications",
        status_code=status.HTTP_201_CREATED,
        response_model=FinancialReportPublicationResponse,
        responses={
            200: {"description": "Rejeu idempotent de la publication."},
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Publication financière réservée au patron."},
            404: {"description": "Rapport absent ou hors tenant."},
            409: {"description": "Conflit de révision ou d’idempotence."},
            422: {"description": "Invariant de publication refusé."},
        },
    )
    def publish_financial_report(
        case_id: UUID,
        report_id: UUID,
        request: PublishFinancialReportRequest,
        authorization: str | None = Header(default=None),
    ) -> FinancialReportPublicationResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            result = publication_service.publish(
                actor=context,
                command=request.to_command(case_id=case_id, report_id=report_id),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
        except CommandExecutionError as error:
            if str(error) == "VERSION_CONFLICT":
                raise HTTPException(status_code=409, detail="VERSION_CONFLICT") from error
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=422, detail="COMMAND_REJECTED") from error
        receipt = FinancialReportPublicationResponse(
            command_id=result.command_id,
            idempotency_key=result.idempotency_key,
            result_code=result.result_code,
            aggregate_refs=list(result.aggregate_refs),
            event_ids=list(result.event_ids),
            replayed=result.replayed,
        )
        return JSONResponse(
            status_code=200 if result.replayed else 201,
            content=receipt.model_dump(mode="json"),
        )

    @router.get(
        "/cases/{case_id}/financial-reports/{report_id}/draft",
        response_model=PatronFinancialReportDraftResponse,
        responses={
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Accès financier patron insuffisant."},
            404: {"description": "Brouillon absent, publié ou hors tenant."},
            422: {"description": "UUID invalide."},
        },
    )
    def get_financial_report_draft(
        case_id: UUID,
        report_id: UUID,
        response: Response,
        authorization: str | None = Header(default=None),
    ) -> PatronFinancialReportDraftResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            report = service.get_draft(
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
        return PatronFinancialReportDraftResponse(
            report_id=report.report_id,
            case_id=report.case_id,
            status="DRAFT",
            aggregate_revision=report.aggregate_revision,
            currency_code=report.currency_code,
            calculated_at=report.calculated_at,
            ruleset_version=report.ruleset_version,
            summary=PatronFinancialReportSummaryResponse(**report.summary),
            lines=[PatronFinancialReportLineResponse(**asdict(line)) for line in report.lines],
        )

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

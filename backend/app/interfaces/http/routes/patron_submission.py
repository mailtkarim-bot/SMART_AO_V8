from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.submission.application.service import SubmissionPackageService
from app.modules.submission.public.contracts import (
    PrepareSubmissionPackageRequest,
    SubmissionPackageCommandResponse,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)


def build_patron_submission_router(
    *,
    service: SubmissionPackageService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron", tags=["patron-submission"])

    @router.post(
        "/preparation/{preparation_package_id}/submission-packages",
        status_code=status.HTTP_201_CREATED,
        response_model=SubmissionPackageCommandResponse,
        responses={
            200: {"description": "Rejeu idempotent du paquet préparé."},
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Préparation du dépôt réservée au patron habilité."},
            404: {"description": "Package absent ou hors tenant."},
            409: {"description": "Conflit d’idempotence ou de révision."},
            422: {"description": "Préparation incomplète ou prix officiel absent."},
        },
    )
    def prepare_submission_package(
        preparation_package_id: UUID,
        request: PrepareSubmissionPackageRequest,
        authorization: str | None = Header(default=None),
    ) -> SubmissionPackageCommandResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            result = service.prepare(
                actor=context,
                command=request.to_command(preparation_package_id=preparation_package_id),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
        except CommandExecutionError as error:
            if str(error) in {"NOT_FOUND_OR_FORBIDDEN", "DCE_NOT_FOUND_OR_FORBIDDEN"}:
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            if str(error) == "VERSION_CONFLICT":
                raise HTTPException(status_code=409, detail="VERSION_CONFLICT") from error
            raise HTTPException(status_code=422, detail="COMMAND_REJECTED") from error
        response = SubmissionPackageCommandResponse(
            command_id=result.command_id,
            idempotency_key=result.idempotency_key,
            result_code=result.result_code,
            aggregate_refs=list(result.aggregate_refs),
            event_ids=list(result.event_ids),
            replayed=result.replayed,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED,
            content=response.model_dump(mode="json"),
        )

    @router.get(
        "/submission-packages/{submission_package_id}/export",
        responses={
            200: {"description": "Export ZIP déterministe du dossier préparé."},
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Export réservé au patron habilité."},
            404: {"description": "Dossier absent ou hors tenant."},
            422: {"description": "Manifeste ou document technique incohérent."},
            503: {"description": "Stockage privé d’export indisponible."},
        },
    )
    def export_submission_package(
        submission_package_id: UUID,
        authorization: str | None = Header(default=None),
    ) -> StreamingResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            archive = service.export(
                actor=context,
                submission_package_id=submission_package_id,
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        except CommandExecutionError as error:
            raise HTTPException(status_code=422, detail="EXPORT_REJECTED") from error
        except RuntimeError as error:
            if str(error) == "SUBMISSION_EXPORT_STORAGE_NOT_CONFIGURED":
                raise HTTPException(status_code=503, detail="EXPORT_UNAVAILABLE") from error
            raise
        return StreamingResponse(
            iter((archive,)),
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="submission-{submission_package_id}.zip"'
                ),
                "Cache-Control": "no-store",
            },
        )

    return router

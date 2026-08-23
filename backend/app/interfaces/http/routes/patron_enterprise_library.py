from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.enterprise.application.enterprise_library import EnterpriseLibraryService
from app.modules.enterprise.application.enterprise_upload import (
    EnterprisePrivateUploadService,
    EnterpriseUploadAlreadyClaimedError,
    EnterpriseUploadRejectedError,
)
from app.modules.enterprise.public.enterprise_contracts import (
    CreateEnterpriseCompanyRequest,
    EnterpriseCompanyResponse,
    EnterpriseDocumentResponse,
    EnterpriseReceiptResponse,
    EnterpriseUploadResponse,
    PrepareEnterpriseDocumentUploadRequest,
    RegisterEnterpriseDocumentRequest,
    VerifyEnterpriseDocumentRequest,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)

IDEMPOTENCY_KEY_HEADER = Header(default=None, alias="Idempotency-Key")


def _receipt(result) -> EnterpriseReceiptResponse:
    return EnterpriseReceiptResponse(
        status="SUCCEEDED",
        command_id=result.command_id,
        idempotency_key=result.idempotency_key,
        result_code=result.result_code,
        aggregate_refs=list(result.aggregate_refs),
        event_ids=list(result.event_ids),
        replayed=result.replayed,
    )


def _company_response(projection) -> EnterpriseCompanyResponse:
    return EnterpriseCompanyResponse(
        company_id=projection.company_id,
        aggregate_revision=projection.aggregate_revision,
        legal_name=projection.legal_name,
        trade_name=projection.trade_name,
        siren=projection.siren,
        siret=projection.siret,
        vat_number=projection.vat_number,
        address_line1=projection.address_line1,
        postal_code=projection.postal_code,
        city=projection.city,
        country_code=projection.country_code,
        documents=[
            EnterpriseDocumentResponse(
                document_id=document.document_id,
                document_kind=document.document_kind,
                document_label=document.document_label,
                issued_at=document.issued_at,
                expires_at=document.expires_at,
                verification_status=document.verification_status,
                verification_revision=document.verification_revision,
            )
            for document in projection.documents
        ],
    )


def build_patron_enterprise_library_router(
    *,
    service: EnterpriseLibraryService,
    upload_service: EnterprisePrivateUploadService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron/enterprise", tags=["patron-enterprise-library"])

    @router.post(
        "/company",
        status_code=status.HTTP_201_CREATED,
        response_model=EnterpriseReceiptResponse,
        responses={
            200: {"description": "Rejeu idempotent de la création."},
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Bibliothèque entreprise réservée au patron."},
            409: {"description": "Conflit d’idempotence ou société déjà créée."},
            422: {"description": "Invariant de société refusé."},
        },
    )
    def create_company(
        request: CreateEnterpriseCompanyRequest,
        authorization: str | None = Header(default=None),
    ) -> EnterpriseReceiptResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            result = service.create_company(
                actor=context,
                command=request.to_command(),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
        except CommandExecutionError as error:
            if str(error) == "ENTERPRISE_COMPANY_ALREADY_EXISTS":
                raise HTTPException(status_code=409, detail="COMPANY_ALREADY_EXISTS") from error
            raise HTTPException(status_code=422, detail="COMMAND_REJECTED") from error
        receipt = _receipt(result)
        return JSONResponse(
            status_code=200 if result.replayed else 201,
            content=receipt.model_dump(mode="json"),
        )

    @router.post(
        "/companies/{company_id}/documents",
        status_code=status.HTTP_201_CREATED,
        response_model=EnterpriseReceiptResponse,
        responses={
            200: {"description": "Rejeu idempotent de l’enregistrement."},
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Bibliothèque entreprise réservée au patron."},
            404: {"description": "Société absente ou hors tenant."},
            409: {"description": "Conflit de révision ou d’idempotence."},
            422: {"description": "Invariant documentaire refusé."},
        },
    )
    def register_document(
        company_id: UUID,
        request: RegisterEnterpriseDocumentRequest,
        authorization: str | None = Header(default=None),
    ) -> EnterpriseReceiptResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            result = service.register_document(
                actor=context,
                command=request.to_command(company_id=company_id),
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
        receipt = _receipt(result)
        return JSONResponse(
            status_code=200 if result.replayed else 201,
            content=receipt.model_dump(mode="json"),
        )

    @router.get(
        "/company",
        response_model=EnterpriseCompanyResponse,
        responses={
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Bibliothèque entreprise réservée au patron."},
            404: {"description": "Société absente ou hors tenant."},
        },
    )
    def read_company(
        authorization: str | None = Header(default=None),
    ) -> EnterpriseCompanyResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            projection = service.read_company(actor=context, now=datetime.now(tz=UTC))
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        return _company_response(projection)

    @router.post(
        "/companies/{company_id}/documents/upload",
        status_code=status.HTTP_201_CREATED,
        response_model=EnterpriseReceiptResponse,
    )
    def prepare_document_upload(
        company_id: UUID,
        request: PrepareEnterpriseDocumentUploadRequest,
        authorization: str | None = Header(default=None),
    ) -> EnterpriseReceiptResponse:
        context = _resolve_context(
            authorization=authorization, context_resolver=security_runtime.context_resolver
        )
        try:
            result = upload_service.prepare(
                actor=context,
                command=request.to_command(company_id=company_id),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
        except CommandExecutionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=422, detail="COMMAND_REJECTED") from error
        receipt = _receipt(result)
        return JSONResponse(
            status_code=200 if result.replayed else 201, content=receipt.model_dump(mode="json")
        )

    @router.put(
        "/companies/{company_id}/documents/uploads/{upload_id}/content",
        response_model=EnterpriseUploadResponse,
    )
    async def upload_document_content(
        company_id: UUID,
        upload_id: UUID,
        request: Request,
        authorization: str | None = Header(default=None),
        idempotency_key: UUID | None = IDEMPOTENCY_KEY_HEADER,
    ) -> EnterpriseUploadResponse:
        context = _resolve_context(
            authorization=authorization, context_resolver=security_runtime.context_resolver
        )
        if idempotency_key is None:
            raise HTTPException(status_code=400, detail="IDEMPOTENCY_KEY_REQUIRED")
        target = upload_service.target(tenant_id=context.tenant_id, upload_id=upload_id)
        if target is None or target.company_id != company_id:
            raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN")
        try:
            result = await upload_service.upload(
                actor=context,
                upload_id=upload_id,
                stream=request.stream(),
                content_length=_content_length(request.headers.get("content-length")),
            )
        except PermissionError as error:
            raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
        except EnterpriseUploadAlreadyClaimedError as error:
            raise HTTPException(status_code=409, detail="UPLOAD_NOT_AWAITING") from error
        except EnterpriseUploadRejectedError as error:
            raise HTTPException(status_code=error.status_code, detail="UPLOAD_REJECTED") from error
        return EnterpriseUploadResponse(upload_id=result.upload_id, state="CLEAN")

    @router.post(
        "/companies/{company_id}/documents/{document_id}/verification",
        response_model=EnterpriseReceiptResponse,
    )
    def verify_document(
        company_id: UUID,
        document_id: UUID,
        request: VerifyEnterpriseDocumentRequest,
        authorization: str | None = Header(default=None),
    ) -> EnterpriseReceiptResponse:
        context = _resolve_context(
            authorization=authorization, context_resolver=security_runtime.context_resolver
        )
        try:
            result = upload_service.verify(
                actor=context,
                command=request.to_command(company_id=company_id, document_id=document_id),
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
        return _receipt(result)

    return router


def _content_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="INVALID_CONTENT_LENGTH") from error
    if parsed < 0:
        raise HTTPException(status_code=400, detail="INVALID_CONTENT_LENGTH")
    return parsed

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile, status

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.pricing.application.import_preview import PricingImportPreviewService
from app.modules.pricing.public.import_contracts import (
    PricingImportPreviewResponse,
    PricingImportRowResponse,
)


async def _read_upload(upload: UploadFile) -> bytes:
    return await upload.read()


def build_patron_pricing_import_router(
    *, service: PricingImportPreviewService, security_runtime: ConsultationSecurityRuntime
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron", tags=["patron-pricing-import"])

    @router.post(
        "/cases/{case_id}/pricing-import/preview",
        response_model=PricingImportPreviewResponse,
        status_code=status.HTTP_200_OK,
    )
    async def preview_import(
        case_id: UUID,
        upload: Annotated[UploadFile, File(...)],
        document_kind: Literal["DPGF", "BPU", "EXCEL"] = Query(default="EXCEL"),
        authorization: str | None = Header(default=None),
    ) -> PricingImportPreviewResponse:
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            preview = service.preview(
                actor=actor,
                case_id=case_id,
                document_kind=document_kind,
                filename=upload.filename or "upload.xlsx",
                content_type=upload.content_type,
                payload=await _read_upload(upload),
            )
        except PermissionError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
            ) from error
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error
        return PricingImportPreviewResponse(
            case_id=preview.case_id,
            document_kind=preview.document_kind,
            filename=preview.filename,
            row_count=preview.row_count,
            valid_row_count=preview.valid_row_count,
            error_count=preview.error_count,
            total_minor=preview.total_minor,
            rows=[
                PricingImportRowResponse(
                    row_number=row.row_number,
                    code=row.code,
                    designation=row.designation,
                    unit=row.unit,
                    quantity_decimal=row.quantity_decimal,
                    unit_price_minor=row.unit_price_minor,
                    total_minor=row.total_minor,
                    errors=list(row.errors),
                )
                for row in preview.rows
            ],
        )

    return router

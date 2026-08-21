from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, File, Header, HTTPException, Query, Response, UploadFile, status

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.pricing.application.import_commands import (
    CommitPricingImportCommand,
    CreatePricingImportPreviewCommand,
    CreatePricingImportRowCommand,
)
from app.modules.pricing.application.import_creation import PricingImportCreationService
from app.modules.pricing.application.import_preview import PricingImportPreviewService
from app.modules.pricing.application.import_service import PricingImportService
from app.modules.pricing.public.import_contracts import (
    CommitPricingImportRequest,
    PricingImportAggregateReferenceResponse,
    PricingImportCommitResponse,
    PricingImportCreationRequest,
    PricingImportPreviewResponse,
    PricingImportRowResponse,
)
from app.platform.events.dispatcher import CommandExecutionError


async def _read_upload(upload: UploadFile) -> bytes:
    return await upload.read()


def build_patron_pricing_import_router(
    *,
    service: PricingImportPreviewService,
    security_runtime: ConsultationSecurityRuntime,
    commit_service: PricingImportService | None = None,
    creation_service: PricingImportCreationService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron", tags=["patron-pricing-import"])

    @router.post(
        "/cases/{case_id}/pricing-import/preview",
        response_model=PricingImportPreviewResponse,
        status_code=status.HTTP_200_OK,
    )
    async def preview_import(
        case_id: UUID,
        response: Response,
        upload: Annotated[UploadFile, File(...)],
        document_kind: Literal["DPGF", "BPU", "EXCEL"] = Query(default="EXCEL"),
        authorization: str | None = Header(default=None),
        command_id: UUID | None = Header(default=None, alias="X-Command-Id"),  # noqa: B008
        idempotency_key: UUID | None = Header(default=None, alias="Idempotency-Key"),  # noqa: B008
        correlation_id: UUID | None = Header(default=None, alias="X-Correlation-Id"),  # noqa: B008
    ) -> PricingImportPreviewResponse:
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        payload = await _read_upload(upload)
        try:
            preview = service.preview(
                actor=actor,
                case_id=case_id,
                document_kind=document_kind,
                filename=upload.filename or "upload.xlsx",
                content_type=upload.content_type,
                payload=payload,
            )
        except PermissionError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
            ) from error
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error

        receipt = None
        if creation_service is not None:
            if command_id is None or idempotency_key is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="COMMAND_METADATA_REQUIRED",
                )
            try:
                request = PricingImportCreationRequest(
                    command_id=command_id,
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                )
                receipt = creation_service.create(
                    actor=actor,
                    command=CreatePricingImportPreviewCommand(
                        command_id=request.command_id,
                        idempotency_key=request.idempotency_key,
                        correlation_id=request.correlation_id,
                        case_id=case_id,
                        document_kind=document_kind,
                        source_sha256=sha256(payload).hexdigest(),
                        rows=[
                            CreatePricingImportRowCommand(
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
                    ),
                    now=datetime.now(tz=UTC),
                )
            except PermissionError as error:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
                ) from error
            except CommandExecutionError as error:
                code = str(error)
                if code in {"NOT_FOUND_OR_FORBIDDEN", "IMPORT_NOT_FOUND_OR_FORBIDDEN"}:
                    http_status = status.HTTP_404_NOT_FOUND
                elif "IDEMPOTENCY" in code or code in {"COMMAND_IN_PROGRESS"}:
                    http_status = status.HTTP_409_CONFLICT
                else:
                    http_status = status.HTTP_422_UNPROCESSABLE_CONTENT
                raise HTTPException(status_code=http_status, detail=code) from error

            if response is not None:
                response.status_code = (
                    status.HTTP_200_OK if receipt.replayed else status.HTTP_201_CREATED
                )

        preview_response = PricingImportPreviewResponse(
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
        if receipt is None:
            return preview_response
        batch_reference = next(
            reference
            for reference in receipt.aggregate_refs
            if reference["aggregate_type"] == "PricingImportBatch"
        )
        return preview_response.model_copy(
            update={
                "batch_id": UUID(str(batch_reference["aggregate_id"])),
                "state": "PREVIEWED",
                "aggregate_revision": int(batch_reference["aggregate_revision"]),
                "result_code": receipt.result_code,
                "command_id": UUID(receipt.command_id),
                "idempotency_key": UUID(receipt.idempotency_key),
                "event_ids": [UUID(event_id) for event_id in receipt.event_ids],
                "replayed": receipt.replayed,
            }
        )

    if commit_service is not None:

        @router.post(
            "/cases/{case_id}/pricing-import/{batch_id}/commit",
            response_model=PricingImportCommitResponse,
            status_code=status.HTTP_201_CREATED,
        )
        def commit_import(
            case_id: UUID,
            batch_id: UUID,
            request: CommitPricingImportRequest,
            authorization: str | None = Header(default=None),
        ) -> PricingImportCommitResponse:
            actor = _resolve_context(
                authorization=authorization,
                context_resolver=security_runtime.context_resolver,
            )
            try:
                receipt = commit_service.commit(
                    actor=actor,
                    command=CommitPricingImportCommand(
                        command_id=request.command_id,
                        idempotency_key=request.idempotency_key,
                        correlation_id=request.correlation_id,
                        case_id=case_id,
                        batch_id=batch_id,
                        report_id=request.report_id,
                        expected_batch_revision=request.expected_batch_revision,
                        expected_report_revision=request.expected_report_revision,
                    ),
                    now=datetime.now(tz=UTC),
                )
            except PermissionError as error:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
                ) from error
            except CommandExecutionError as error:
                code = str(error)
                if code in {
                    "IMPORT_NOT_FOUND_OR_FORBIDDEN",
                    "FINANCIAL_REPORT_NOT_FOUND_OR_FORBIDDEN",
                }:
                    http_status = status.HTTP_404_NOT_FOUND
                elif code in {"VERSION_CONFLICT", "IMPORT_ALREADY_COMMITTED"}:
                    http_status = status.HTTP_409_CONFLICT
                else:
                    http_status = status.HTTP_422_UNPROCESSABLE_CONTENT
                raise HTTPException(status_code=http_status, detail=code) from error
            return PricingImportCommitResponse(
                command_id=UUID(receipt.command_id),
                idempotency_key=UUID(receipt.idempotency_key),
                result_code=receipt.result_code,
                aggregate_refs=[
                    PricingImportAggregateReferenceResponse(**reference)
                    for reference in receipt.aggregate_refs
                ],
                event_ids=[UUID(event_id) for event_id in receipt.event_ids],
                replayed=receipt.replayed,
            )

    return router

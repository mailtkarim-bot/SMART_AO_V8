from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.preparation.application.commands import (
    EvaluatePreparationReadinessCommand,
    GenerateTechnicalDocumentCommand,
)
from app.modules.preparation.application.review import PreparationReviewService
from app.modules.preparation.application.review_commands import (
    AddPreparationCorrectionCommand,
    CreateTechnicalResponseDraftCommand,
    DecidePreparationReviewCommand,
    RequestPreparationReviewCommand,
)
from app.modules.preparation.application.service import PreparationService
from app.modules.preparation.public.contracts import (
    AddPreparationCorrectionRequest,
    CreateTechnicalResponseDraftRequest,
    DecidePreparationReviewRequest,
    EvaluatePreparationReadinessRequest,
    GeneratedDocumentProjection,
    GenerateTechnicalDocumentRequest,
    PreparationAggregateReference,
    PreparationCommandResponse,
    PreparationPackageProjection,
    PreparationReadinessProjection,
    RequestPreparationReviewRequest,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)


def build_preparation_router(
    *, service: PreparationService, security_runtime: ConsultationSecurityRuntime
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/collaborator", tags=["preparation"])

    @router.get("/preparation/{package_id}", response_model=PreparationPackageProjection)
    def read_package(
        package_id: UUID,
        authorization: str | None = Header(default=None),
    ) -> PreparationPackageProjection:
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            package, readiness, documents = service.read_package(
                actor=actor, package_id=package_id, now=datetime.now(tz=UTC)
            )
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="NOT_FOUND_OR_FORBIDDEN"
                ) from error
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
            ) from error
        return PreparationPackageProjection(
            package_id=package.id,
            case_id=package.case_id,
            assignment_id=package.assignment_id,
            dce_version_id=package.dce_version_id,
            state=package.state,
            aggregate_revision=package.aggregate_revision,
            latest_readiness=(
                PreparationReadinessProjection(
                    readiness_id=readiness.id,
                    revision=readiness.revision,
                    state=readiness.state,
                    blocker_codes=list(readiness.blocker_codes_json),
                    warning_codes=list(readiness.warning_codes_json),
                    checked_requirement_count=readiness.checked_requirement_count,
                    checked_task_count=readiness.checked_task_count,
                )
                if readiness is not None
                else None
            ),
            generated_documents=[
                GeneratedDocumentProjection(
                    document_id=document.id,
                    version=document.version,
                    document_kind=document.document_kind,
                    state=document.state,
                    readiness_revision=_readiness_revision(document=document, readiness=readiness),
                )
                for document in documents
            ],
        )

    @router.post(
        "/cases/{case_id}/preparation/readiness",
        status_code=status.HTTP_201_CREATED,
        response_model=PreparationCommandResponse,
    )
    def evaluate_readiness(
        case_id: UUID,
        request: EvaluatePreparationReadinessRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service=service,
            actor=actor,
            command=EvaluatePreparationReadinessCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                package_id=request.package_id,
                case_id=case_id,
                assignment_id=request.assignment_id,
                dce_version_id=request.dce_version_id,
                expected_revision=request.expected_revision,
            ),
        )

    @router.post(
        "/preparation/{package_id}/documents",
        status_code=status.HTTP_201_CREATED,
        response_model=PreparationCommandResponse,
    )
    def generate_document(
        package_id: UUID,
        request: GenerateTechnicalDocumentRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service=service,
            actor=actor,
            command=GenerateTechnicalDocumentCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                package_id=package_id,
                document_id=request.command_id,
                expected_revision=request.expected_revision,
                readiness_revision=request.readiness_revision,
                document_kind=request.document_kind,
            ),
        )

    return router


def build_preparation_review_router(
    *, service: PreparationReviewService, security_runtime: ConsultationSecurityRuntime
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/preparation", tags=["preparation-review"])

    @router.post("/{package_id}/reviews", response_model=PreparationCommandResponse)
    def request_review(
        package_id: UUID,
        request: RequestPreparationReviewRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch_review(
            service=service,
            actor=actor,
            command=RequestPreparationReviewCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                review_id=request.review_id,
                package_id=package_id,
                target_document_id=request.target_document_id,
                target_version=request.target_version,
                expected_package_revision=request.expected_package_revision,
            ),
        )

    @router.post(
        "/{package_id}/reviews/{review_id}/decision",
        response_model=PreparationCommandResponse,
    )
    def decide_review(
        package_id: UUID,
        review_id: UUID,
        request: DecidePreparationReviewRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch_review(
            service=service,
            actor=actor,
            command=DecidePreparationReviewCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                review_id=review_id,
                package_id=package_id,
                target_document_id=request.target_document_id,
                expected_review_revision=request.expected_review_revision,
                decision_code=request.decision_code,
                decision_note=request.decision_note,
            ),
        )

    @router.post(
        "/{package_id}/reviews/{review_id}/corrections",
        response_model=PreparationCommandResponse,
    )
    def add_correction(
        package_id: UUID,
        review_id: UUID,
        request: AddPreparationCorrectionRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch_review(
            service=service,
            actor=actor,
            command=AddPreparationCorrectionCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                review_id=review_id,
                package_id=package_id,
                target_document_id=request.target_document_id,
                correction_code=request.correction_code,
                instruction=request.instruction,
                source_locator=request.source_locator,
            ),
        )

    @router.post("/{package_id}/response-drafts", response_model=PreparationCommandResponse)
    def create_response_draft(
        package_id: UUID,
        request: CreateTechnicalResponseDraftRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch_review(
            service=service,
            actor=actor,
            command=CreateTechnicalResponseDraftCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                draft_id=request.draft_id,
                package_id=package_id,
                source_document_id=request.source_document_id,
                expected_package_revision=request.expected_package_revision,
                section_codes=request.section_codes,
                source_refs=request.source_refs,
            ),
        )

    return router


def _dispatch_review(*, service: PreparationReviewService, actor, command):
    try:
        result = service.execute(actor=actor, command=command, now=datetime.now(tz=UTC))
    except PermissionError as error:
        if str(error) == "NOT_FOUND_OR_FORBIDDEN":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="NOT_FOUND_OR_FORBIDDEN"
            ) from error
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN") from error
    except IdempotencyKeyReusedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="IDEMPOTENCY_KEY_REUSED"
        ) from error
    except CommandInProgressError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="COMMAND_IN_PROGRESS"
        ) from error
    except CommandExecutionError as error:
        detail = str(error)
        code = (
            status.HTTP_409_CONFLICT
            if detail == "VERSION_CONFLICT"
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=code, detail=detail) from error
    response = PreparationCommandResponse(
        command_id=result.command_id,
        idempotency_key=result.idempotency_key,
        result_code=result.result_code,
        aggregate_refs=[PreparationAggregateReference(**ref) for ref in result.aggregate_refs],
        event_ids=list(result.event_ids),
        replayed=result.replayed,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED,
        content=response.model_dump(mode="json"),
    )


def _readiness_revision(*, document, readiness) -> int:
    if readiness is not None and readiness.id == document.readiness_id:
        return readiness.revision
    return 0


def _dispatch(*, service: PreparationService, actor, command):
    try:
        result = service.execute(actor=actor, command=command, now=datetime.now(tz=UTC))
    except PermissionError as error:
        if str(error) == "NOT_FOUND_OR_FORBIDDEN":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="NOT_FOUND_OR_FORBIDDEN"
            ) from error
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN") from error
    except IdempotencyKeyReusedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="IDEMPOTENCY_KEY_REUSED"
        ) from error
    except CommandInProgressError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="COMMAND_IN_PROGRESS"
        ) from error
    except CommandExecutionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    response = PreparationCommandResponse(
        command_id=result.command_id,
        idempotency_key=result.idempotency_key,
        result_code=result.result_code,
        aggregate_refs=[PreparationAggregateReference(**ref) for ref in result.aggregate_refs],
        event_ids=list(result.event_ids),
        replayed=result.replayed,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED,
        content=response.model_dump(mode="json"),
    )

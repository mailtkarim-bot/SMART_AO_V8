from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.submission.application.evidence_commands import RecordSubmissionEvidenceCommand
from app.modules.submission.application.evidence_service import SubmissionEvidenceService
from app.modules.submission.public.evidence_contracts import (
    RecordSubmissionEvidenceRequest,
    SubmissionEvidenceCommandResponse,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)


def build_patron_submission_evidence_router(
    *, service: SubmissionEvidenceService, security_runtime: ConsultationSecurityRuntime
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron", tags=["patron-submission"])

    @router.post(
        "/submission-packages/{submission_package_id}/evidence",
        response_model=SubmissionEvidenceCommandResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def record_evidence(
        submission_package_id: UUID,
        request: RecordSubmissionEvidenceRequest,
        authorization: str | None = Header(default=None),
    ) -> SubmissionEvidenceCommandResponse:
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            result = service.execute(
                actor=actor,
                command=RecordSubmissionEvidenceCommand(
                    command_id=request.command_id,
                    idempotency_key=request.idempotency_key,
                    correlation_id=request.correlation_id,
                    evidence_id=request.evidence_id,
                    submission_package_id=submission_package_id,
                    evidence_type=request.evidence_type,
                    external_reference_hash=request.external_reference_hash,
                    evidence_sha256=request.evidence_sha256,
                    notes_redacted=request.notes_redacted,
                ),
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
        response = SubmissionEvidenceCommandResponse(
            command_id=result.command_id,
            idempotency_key=result.idempotency_key,
            result_code=result.result_code,
            aggregate_refs=list(result.aggregate_refs),
            event_ids=list(result.event_ids),
            replayed=result.replayed,
        )
        return JSONResponse(
            status_code=200 if result.replayed else 201,
            content=response.model_dump(mode="json"),
        )

    return router

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.submission.application.signature_commands import (
    RecordSubmissionSignatureCommand,
    RequestSubmissionSignatureCommand,
)
from app.modules.submission.application.signature_service import (
    SubmissionSignatureReadService,
    SubmissionSignatureService,
)
from app.modules.submission.public.signature_contracts import (
    RecordSubmissionSignatureCallbackRequest,
    RequestSubmissionSignatureRequest,
    SubmissionSignatureCommandResponse,
    SubmissionSignatureProjection,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)
from app.platform.security.authenticated_context import UnauthenticatedError


def build_patron_submission_signature_router(
    *,
    service: SubmissionSignatureService,
    read_service: SubmissionSignatureReadService,
    security_runtime: ConsultationSecurityRuntime,
    callback_secret: str,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron", tags=["patron-submission-signature"])

    @router.post(
        "/submission-packages/{submission_package_id}/signatures",
        response_model=SubmissionSignatureCommandResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def request_signature(
        submission_package_id: UUID,
        request: RequestSubmissionSignatureRequest,
        authorization: str | None = Header(default=None),
    ) -> SubmissionSignatureCommandResponse:
        actor = _resolve_actor(authorization=authorization, security_runtime=security_runtime)
        try:
            result = service.execute(
                actor=actor,
                command=RequestSubmissionSignatureCommand(
                    command_id=request.command_id,
                    idempotency_key=request.idempotency_key,
                    correlation_id=request.correlation_id,
                    signature_id=request.signature_id,
                    submission_package_id=submission_package_id,
                    expected_package_version=request.expected_package_version,
                    signer_membership_id=actor.membership_id,
                    provider=service.provider,
                ),
                now=datetime.now(tz=UTC),
            )
        except Exception as error:
            _raise_http_error(error)
        return _command_response(result)

    @router.post(
        "/submission-signatures/{signature_id}/callback",
        response_model=SubmissionSignatureCommandResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def record_callback(
        signature_id: UUID,
        payload: RecordSubmissionSignatureCallbackRequest,
        request: Request,
        authorization: str | None = Header(default=None),
        x_signature_callback: str | None = Header(default=None),
    ) -> SubmissionSignatureCommandResponse:
        _verify_callback_signature(
            secret=callback_secret,
            signature_header=x_signature_callback,
            body=await request.body(),
        )
        actor = _resolve_actor(authorization=authorization, security_runtime=security_runtime)
        try:
            result = service.execute(
                actor=actor,
                command=RecordSubmissionSignatureCommand(
                    command_id=payload.delivery_id,
                    idempotency_key=payload.delivery_id,
                    correlation_id=payload.delivery_id,
                    signature_id=signature_id,
                    submission_package_id=payload.submission_package_id,
                    provider=payload.provider,
                    provider_reference_hash=payload.provider_reference_hash,
                    signature_sha256=payload.signature_sha256,
                    outcome=payload.outcome,
                ),
                now=datetime.now(tz=UTC),
            )
        except Exception as error:
            _raise_http_error(error)
        return _command_response(result)

    @router.get(
        "/submission-signatures/{signature_id}",
        response_model=SubmissionSignatureProjection,
    )
    def read_signature(
        signature_id: UUID,
        authorization: str | None = Header(default=None),
    ) -> SubmissionSignatureProjection:
        actor = _resolve_actor(authorization=authorization, security_runtime=security_runtime)
        try:
            return read_service.read(
                actor=actor,
                signature_id=signature_id,
                now=datetime.now(tz=UTC),
            )
        except Exception as error:
            _raise_http_error(error)
        raise AssertionError("unreachable")

    return router


def _resolve_actor(*, authorization: str | None, security_runtime: ConsultationSecurityRuntime):
    try:
        return _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
    except UnauthenticatedError as error:
        raise HTTPException(status_code=401, detail="UNAUTHENTICATED") from error


def _verify_callback_signature(
    *,
    secret: str,
    signature_header: str | None,
    body: bytes,
) -> None:
    normalized_secret = secret.strip()
    if len(normalized_secret) < 32:
        raise HTTPException(status_code=503, detail="SIGNATURE_CALLBACK_UNAVAILABLE")
    if signature_header is None or not signature_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="CALLBACK_UNAUTHENTICATED")
    received = signature_header.removeprefix("sha256=").strip()
    if len(received) != 64 or any(character not in "0123456789abcdef" for character in received):
        raise HTTPException(status_code=401, detail="CALLBACK_UNAUTHENTICATED")
    expected = hmac.new(normalized_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise HTTPException(status_code=401, detail="CALLBACK_UNAUTHENTICATED")


def _command_response(result) -> JSONResponse:
    response = SubmissionSignatureCommandResponse(
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


def _raise_http_error(error: Exception) -> None:
    if isinstance(error, PermissionError):
        raise HTTPException(status_code=403, detail="FORBIDDEN") from error
    if isinstance(error, (IdempotencyKeyReusedError, CommandInProgressError)):
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
    if isinstance(error, CommandExecutionError):
        if str(error) == "NOT_FOUND_OR_FORBIDDEN":
            raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
        raise HTTPException(status_code=422, detail="COMMAND_REJECTED") from error
    raise error

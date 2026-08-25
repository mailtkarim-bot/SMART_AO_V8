"""Patron-authorized Case creation entrypoint."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.aggregate_refs import require_aggregate_revision
from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.case.application.commands import CreateCaseCommand
from app.modules.case.public.contracts import CreateCaseRequest, CreateCaseResponse
from app.platform.events.dispatcher import (
    CommandDispatcher,
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)
from app.platform.security.authorization import AuthorizationRequest, AuthorizationResource
from app.platform.security.capabilities import Capability
from app.platform.security.context import DataClassification


def build_case_creation_router(
    *, dispatcher: CommandDispatcher, security_runtime: ConsultationSecurityRuntime
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/cases", tags=["cases"])

    @router.post("", response_model=CreateCaseResponse)
    def create_case(
        request: CreateCaseRequest,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        case_id = uuid5(NAMESPACE_URL, f"smart-ao:case:{request.idempotency_key}")
        decision = security_runtime.policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.CASE_CREATE,
                resource=AuthorizationResource(
                    resource_type="CASE",
                    resource_id=case_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=case_id,
                ),
                evaluated_at=datetime.now(tz=UTC),
            ),
        )
        if not decision.allowed:
            raise HTTPException(status_code=decision.http_status_code, detail=decision.code)

        try:
            result = dispatcher.dispatch(
                command=CreateCaseCommand(
                    command_id=request.command_id,
                    idempotency_key=request.idempotency_key,
                    correlation_id=request.correlation_id,
                    case_id=case_id,
                    title=request.title,
                    object_description=request.object_description,
                    consultation_id=request.consultation_id,
                    consultation_revision=request.consultation_revision,
                    scope_kind=request.scope_kind,
                    lot_numbers=request.lot_numbers,
                    tranche_reference=request.tranche_reference,
                    variant_reference=request.variant_reference,
                    scope_justification=request.scope_justification,
                    origin_kind=request.origin_kind,
                    origin_rationale=request.origin_rationale,
                    origin_reference_id=request.origin_reference_id,
                ),
                context=_command_context(actor),
            )
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="IDEMPOTENCY_CONFLICT",
            ) from error
        except CommandExecutionError as error:
            code = _command_error_code(error)
            http_status = (
                status.HTTP_409_CONFLICT
                if code in {"DUPLICATE_FUNCTIONAL_IDENTITY", "VERSION_CONFLICT"}
                else status.HTTP_422_UNPROCESSABLE_CONTENT
            )
            raise HTTPException(status_code=http_status, detail=code) from error

        reference = result.aggregate_refs[0]
        response = CreateCaseResponse(
            command_id=UUID(result.command_id),
            idempotency_key=UUID(result.idempotency_key),
            result_code="CASE_CREATED",
            case_id=UUID(str(reference["aggregate_id"])),
            version=require_aggregate_revision(reference["aggregate_revision"]),
            event_ids=[UUID(event_id) for event_id in result.event_ids],
            replayed=result.replayed,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED,
            content=response.model_dump(mode="json"),
        )

    return router


def _command_context(actor):
    from app.platform.events.dispatcher import CommandContext

    return CommandContext(
        tenant_id=actor.tenant_id,
        actor_id=actor.actor_id,
        actor_kind=actor.actor_kind.value,
        received_at=datetime.now(tz=UTC),
        identity_id=actor.identity_id,
        membership_id=actor.membership_id,
        session_id=actor.session_id,
        correlation_id=actor.correlation_id,
    )


def _command_error_code(error: CommandExecutionError) -> str:
    cause = error.__cause__
    if isinstance(cause, ValueError):
        return str(cause)
    return str(error)

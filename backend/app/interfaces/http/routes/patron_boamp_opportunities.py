from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.interfaces.http.aggregate_refs import require_aggregate_revision
from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.opportunity.application.boamp_case_creation import (
    BoampCaseCreationCommand,
    BoampCaseCreationService,
)
from app.modules.opportunity.application.boamp_qualification import (
    BoampQualificationCommand,
    PatronBoampObservationService,
    QualificationDecision,
    QualificationReason,
)
from app.modules.opportunity.application.boamp_qualification_errors import (
    BoampQualificationIdempotencyConflict,
)
from app.modules.opportunity.public.boamp_qualification_contracts import (
    BoampCaseCreationResponse,
    BoampObservationCreateCaseRequest,
    BoampObservationListResponse,
    BoampObservationQualificationRequest,
    BoampObservationResponse,
    BoampQualificationReceiptResponse,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)
from app.platform.security.authorization import AuthorizationRequest, AuthorizationResource
from app.platform.security.capabilities import Capability
from app.platform.security.context import DataClassification


def build_patron_boamp_opportunity_router(
    *,
    runtime,
    security_runtime: ConsultationSecurityRuntime,
    case_creation_service: BoampCaseCreationService | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/patron/boamp-opportunities",
        tags=["patron-boamp-opportunities"],
    )
    service = PatronBoampObservationService(
        repository=runtime.boamp_qualification_repository
    )

    @router.get("", response_model=BoampObservationListResponse)
    def read_observations(
        authorization: str | None = Header(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        min_score: int = Query(default=0, ge=0, le=100),
    ) -> BoampObservationListResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        _authorize(
            context=context,
            security_runtime=security_runtime,
            action=Capability.OPPORTUNITY_OBSERVATION_READ,
            resource_id=context.tenant_id,
        )
        try:
            with runtime.session_factory() as session:
                observations = service.read(
                    session=session,
                    tenant_id=context.tenant_id,
                    actor_id=context.actor_id,
                    actor_kind=context.actor_kind.value,
                    limit=limit,
                    min_score=min_score,
                )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        return BoampObservationListResponse(
            observations=[_observation_response(item) for item in observations]
        )

    @router.post(
        "/{observation_id}/qualification",
        response_model=BoampQualificationReceiptResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Capability réservée au patron."},
            404: {"description": "Observation absente ou hors tenant."},
            409: {"description": "Conflit d’idempotence."},
            422: {"description": "Décision ou motif incompatible."},
        },
    )
    def qualify_observation(
        observation_id: UUID,
        request: BoampObservationQualificationRequest,
        authorization: str | None = Header(default=None),
    ) -> BoampQualificationReceiptResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        _authorize(
            context=context,
            security_runtime=security_runtime,
            action=Capability.OPPORTUNITY_OBSERVATION_QUALIFY,
            resource_id=observation_id,
        )
        command = BoampQualificationCommand(
            observation_id=observation_id,
            decision=QualificationDecision(request.decision),
            reason_code=QualificationReason(request.reason_code),
            command_id=request.command_id,
            idempotency_key=request.idempotency_key,
            correlation_id=request.correlation_id,
        )
        command_context = CommandContext(
            tenant_id=context.tenant_id,
            actor_id=context.actor_id,
            actor_kind=context.actor_kind.value,
            received_at=datetime.now(tz=UTC),
            identity_id=context.identity_id,
            membership_id=context.membership_id,
            session_id=context.session_id,
            correlation_id=context.correlation_id,
        )
        try:
            with runtime.session_factory.begin() as session:
                result = service.qualify(
                    session=session,
                    context=command_context,
                    command=command,
                    now=datetime.now(tz=UTC),
                )
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail="INVALID_QUALIFICATION") from error
        except BoampQualificationIdempotencyConflict as error:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
        response = BoampQualificationReceiptResponse(
            qualification_id=result.qualification_id,
            event_id=result.event_id,
            replayed=result.replayed,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED,
            content=response.model_dump(mode="json"),
        )

    @router.post(
        "/{observation_id}/case",
        response_model=BoampCaseCreationResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Capability réservée au patron."},
            404: {"description": "Observation absente ou hors tenant."},
            409: {"description": "Conflit d’idempotence ou d’affaire existante."},
            422: {"description": "Qualification préalable ou commande invalide."},
            503: {"description": "Conversion non configurée."},
        },
    )
    def create_case_from_observation(
        observation_id: UUID,
        request: BoampObservationCreateCaseRequest,
        authorization: str | None = Header(default=None),
    ) -> BoampCaseCreationResponse:
        if case_creation_service is None:
            raise HTTPException(status_code=503, detail="BOAMP_CASE_CONVERSION_NOT_CONFIGURED")
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        _authorize(
            context=context,
            security_runtime=security_runtime,
            action=Capability.CASE_CREATE,
            resource_id=observation_id,
        )
        command_context = CommandContext(
            tenant_id=context.tenant_id,
            actor_id=context.actor_id,
            actor_kind=context.actor_kind.value,
            received_at=datetime.now(tz=UTC),
            identity_id=context.identity_id,
            membership_id=context.membership_id,
            session_id=context.session_id,
            correlation_id=context.correlation_id,
        )
        try:
            result = case_creation_service.create(
                context=command_context,
                command=BoampCaseCreationCommand(
                    observation_id=observation_id,
                    command_id=request.command_id,
                    idempotency_key=request.idempotency_key,
                    correlation_id=request.correlation_id,
                ),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
        except CommandExecutionError as error:
            code = str(error.__cause__) if isinstance(error.__cause__, ValueError) else str(error)
            http_status = (
                409
                if code in {"DUPLICATE_FUNCTIONAL_IDENTITY", "VERSION_CONFLICT"}
                else 422
            )
            raise HTTPException(status_code=http_status, detail=code) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        reference = next(
            item for item in result.aggregate_refs if item["aggregate_type"] == "AFF"
        )
        response = BoampCaseCreationResponse(
            command_id=UUID(result.command_id),
            idempotency_key=UUID(result.idempotency_key),
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


def _authorize(*, context, security_runtime, action: Capability, resource_id: UUID) -> None:
    decision = security_runtime.policy.authorize(
        context=context,
        request=AuthorizationRequest(
            action=action,
            resource=AuthorizationResource(
                resource_type="BOAMP_OPPORTUNITY",
                resource_id=resource_id,
                tenant_id=context.tenant_id,
                classification=DataClassification.PUBLIC_TENDER,
            ),
            evaluated_at=datetime.now(tz=UTC),
        ),
    )
    if not decision.allowed:
        raise HTTPException(status_code=decision.http_status_code, detail=decision.code)


def _observation_response(item) -> BoampObservationResponse:
    return BoampObservationResponse(
        observation_id=item.observation_id,
        source_notice_id=item.source_notice_id,
        title=item.title,
        publication_date=item.publication_date,
        response_deadline=item.response_deadline,
        department_codes=list(item.department_codes),
        market_types=list(item.market_types),
        source_status=item.source_status,
        score_version=item.score_version,
        score=item.score,
        score_explanation=item.score_explanation,
        fingerprint_sha256=item.fingerprint_sha256,
    )

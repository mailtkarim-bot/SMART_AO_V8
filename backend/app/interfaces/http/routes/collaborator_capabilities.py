from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.membership.application.collab_capability import (
    CollaboratorCapabilityAssessmentService,
)
from app.modules.membership.public.collab_capability_contracts import (
    CapabilityGapResponse,
    CapabilityProposalResponse,
    CollaboratorCapabilityAssessmentResponse,
    CollaboratorCapabilityReceiptResponse,
    ProposeCapabilityForCaseRequest,
    ReportCapabilityGapRequest,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)


def _receipt(result) -> CollaboratorCapabilityReceiptResponse:
    return CollaboratorCapabilityReceiptResponse(
        status="SUCCEEDED",
        command_id=result.command_id,
        idempotency_key=result.idempotency_key,
        result_code=result.result_code,
        aggregate_refs=list(result.aggregate_refs),
        event_ids=list(result.event_ids),
        replayed=result.replayed,
    )


def build_collaborator_capability_router(
    *,
    service: CollaboratorCapabilityAssessmentService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/collaborator", tags=["collaborator-capabilities"])

    @router.post(
        "/cases/{case_id}/capability-proposals",
        status_code=status.HTTP_201_CREATED,
        response_model=CollaboratorCapabilityReceiptResponse,
        responses={
            200: {"description": "Rejeu idempotent."},
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Affectation ou scope insuffisant."},
            404: {"description": "Ressource absente du tenant."},
            409: {"description": "Conflit d’idempotence ou proposition déjà existante."},
            422: {"description": "Payload ou invariant refusé."},
        },
    )
    def propose_capability(
        case_id: UUID,
        request: ProposeCapabilityForCaseRequest,
        authorization: str | None = Header(default=None),
    ) -> CollaboratorCapabilityReceiptResponse:
        context = _resolve_context(
            authorization=authorization, context_resolver=security_runtime.context_resolver
        )
        try:
            result = service.propose_capability(
                actor=context,
                command=request.to_command(case_id=case_id),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
        except CommandExecutionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            if str(error) in {"SCOPE_DENIED", "ASSIGNMENT_REQUIRED"}:
                raise HTTPException(status_code=403, detail="FORBIDDEN") from error
            if str(error) == "CAPABILITY_PROPOSAL_ALREADY_EXISTS":
                raise HTTPException(
                    status_code=409, detail="CAPABILITY_PROPOSAL_ALREADY_EXISTS"
                ) from error
            raise HTTPException(status_code=422, detail="COMMAND_REJECTED") from error
        receipt = _receipt(result)
        return JSONResponse(
            status_code=200 if result.replayed else 201,
            content=receipt.model_dump(mode="json"),
        )

    @router.post(
        "/cases/{case_id}/capability-gaps",
        status_code=status.HTTP_201_CREATED,
        response_model=CollaboratorCapabilityReceiptResponse,
    )
    def report_gap(
        case_id: UUID,
        request: ReportCapabilityGapRequest,
        authorization: str | None = Header(default=None),
    ) -> CollaboratorCapabilityReceiptResponse:
        context = _resolve_context(
            authorization=authorization, context_resolver=security_runtime.context_resolver
        )
        try:
            result = service.report_gap(
                actor=context,
                command=request.to_command(case_id=case_id),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
        except CommandExecutionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            if str(error) in {"SCOPE_DENIED", "ASSIGNMENT_REQUIRED"}:
                raise HTTPException(status_code=403, detail="FORBIDDEN") from error
            if str(error) == "CAPABILITY_GAP_ALREADY_REPORTED":
                raise HTTPException(
                    status_code=409, detail="CAPABILITY_GAP_ALREADY_REPORTED"
                ) from error
            raise HTTPException(status_code=422, detail="COMMAND_REJECTED") from error
        receipt = _receipt(result)
        return JSONResponse(
            status_code=200 if result.replayed else 201,
            content=receipt.model_dump(mode="json"),
        )

    @router.get(
        "/cases/{case_id}/capability-assessments",
        response_model=CollaboratorCapabilityAssessmentResponse,
        responses={
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Affectation ou scope insuffisant."},
            404: {"description": "Ressource absente du tenant."},
        },
    )
    def read_assessments(
        case_id: UUID,
        assignment_id: UUID,
        authorization: str | None = Header(default=None),
    ) -> CollaboratorCapabilityAssessmentResponse:
        context = _resolve_context(
            authorization=authorization, context_resolver=security_runtime.context_resolver
        )
        try:
            projection = service.read_assessments(
                actor=context,
                case_id=case_id,
                assignment_id=assignment_id,
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        except CommandExecutionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        return CollaboratorCapabilityAssessmentResponse(
            proposals=[
                CapabilityProposalResponse(
                    proposal_id=item.proposal_id,
                    case_id=item.case_id,
                    assignment_id=item.assignment_id,
                    capability_id=item.capability_id,
                    capability_version_id=item.capability_version_id,
                    requirement_id=item.requirement_id,
                    task_id=item.task_id,
                    state=item.state,
                    validity_state=item.validity_state,
                    justification=item.justification,
                    source_locator=item.source_locator,
                )
                for item in projection.proposals
            ],
            gaps=[
                CapabilityGapResponse(
                    gap_id=item.gap_id,
                    case_id=item.case_id,
                    assignment_id=item.assignment_id,
                    capability_id=item.capability_id,
                    requirement_id=item.requirement_id,
                    task_id=item.task_id,
                    gap_kind=item.gap_kind,
                    severity=item.severity,
                    reason=item.reason,
                    source_locator=item.source_locator,
                    recommended_action=item.recommended_action,
                )
                for item in projection.gaps
            ],
        )

    return router

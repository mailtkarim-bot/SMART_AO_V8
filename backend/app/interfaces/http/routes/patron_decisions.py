from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.decision.application.finalize import PatronDecisionFinalizationService
from app.modules.decision.application.finalize_commands import FinalizeGoNoGoDecisionCommand
from app.modules.decision.application.link_commands import LinkRiskToRequirementCommand
from app.modules.decision.application.patron_dossier import PatronDecisionDossierService
from app.modules.decision.application.risk import PatronDecisionRiskService
from app.modules.decision.application.risk_commands import RegisterStructuredRiskCommand
from app.modules.decision.application.risk_requirement import (
    PatronDecisionRiskRequirementService,
)
from app.modules.decision.public.finalize_contracts import (
    FinalizeGoNoGoDecisionRequest,
    FinalizeGoNoGoDecisionResponse,
)
from app.modules.decision.public.patron_contracts import PatronDecisionDossierResponse
from app.modules.decision.public.risk_contracts import (
    RegisterStructuredRiskRequest,
    StructuredRiskCommandResponse,
)
from app.modules.decision.public.risk_requirement_contracts import (
    LinkRiskToRequirementRequest,
    RiskRequirementLinkCommandResponse,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)


def build_patron_decision_router(
    *,
    service: PatronDecisionDossierService,
    security_runtime: ConsultationSecurityRuntime,
    risk_service: PatronDecisionRiskService | None = None,
    risk_requirement_service: PatronDecisionRiskRequirementService | None = None,
    finalization_service: PatronDecisionFinalizationService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron", tags=["patron-decisions"])

    @router.get("/cases/{case_id}/decision-dossier", response_model=PatronDecisionDossierResponse)
    def read_dossier(case_id: UUID, authorization: str | None = Header(default=None)):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            dossier = service.read(actor=actor, case_id=case_id, now=datetime.now(tz=UTC))
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="NOT_FOUND_OR_FORBIDDEN"
                ) from error
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
            ) from error
        payload = asdict(dossier)
        payload["conditions"] = list(payload["conditions"])
        payload["sources"] = list(payload["sources"])
        return PatronDecisionDossierResponse(**payload)

    if risk_service is not None:

        @router.post(
            "/cases/{case_id}/risks",
            response_model=StructuredRiskCommandResponse,
        )
        def register_risk(
            case_id: UUID,
            request: RegisterStructuredRiskRequest,
            authorization: str | None = Header(default=None),
        ):
            actor = _resolve_context(
                authorization=authorization,
                context_resolver=security_runtime.context_resolver,
            )
            try:
                result = risk_service.execute(
                    actor=actor,
                    command=RegisterStructuredRiskCommand(
                        command_id=request.command_id,
                        idempotency_key=request.idempotency_key,
                        correlation_id=request.correlation_id,
                        risk_id=request.risk_id,
                        case_id=case_id,
                        dce_version_id=request.dce_version_id,
                        source_fragment_id=request.source_fragment_id,
                        category=request.category,
                        risk_code=request.risk_code,
                        title=request.title,
                        statement=request.statement,
                        severity=request.severity,
                        likelihood=request.likelihood,
                        source_excerpt=request.source_excerpt,
                        source_locator=request.source_locator,
                        start_byte_offset=request.start_byte_offset,
                        end_byte_offset=request.end_byte_offset,
                        due_at=request.due_at,
                    ),
                    now=datetime.now(tz=UTC),
                )
            except PermissionError as error:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
                ) from error
            except (IdempotencyKeyReusedError, CommandInProgressError) as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="IDEMPOTENCY_CONFLICT"
                ) from error
            except CommandExecutionError as error:
                detail = str(error)
                code = (
                    status.HTTP_409_CONFLICT
                    if detail == "RISK_ALREADY_REGISTERED"
                    else status.HTTP_422_UNPROCESSABLE_CONTENT
                )
                raise HTTPException(status_code=code, detail=detail) from error
            reference = result.aggregate_refs[0]
            response = StructuredRiskCommandResponse(
                command_id=result.command_id,
                idempotency_key=result.idempotency_key,
                result_code=result.result_code,
                risk_id=UUID(str(reference["aggregate_id"])),
                version=int(reference["aggregate_revision"]),
                event_ids=[UUID(event_id) for event_id in result.event_ids],
                replayed=result.replayed,
            )
            return JSONResponse(
                status_code=200 if result.replayed else 201,
                content=response.model_dump(mode="json"),
            )

    if risk_requirement_service is not None:

        @router.post(
            "/cases/{case_id}/risks/{risk_id}/requirements",
            response_model=RiskRequirementLinkCommandResponse,
        )
        def link_risk_to_requirement(
            case_id: UUID,
            risk_id: UUID,
            request: LinkRiskToRequirementRequest,
            authorization: str | None = Header(default=None),
        ):
            actor = _resolve_context(
                authorization=authorization,
                context_resolver=security_runtime.context_resolver,
            )
            try:
                result = risk_requirement_service.execute(
                    actor=actor,
                    command=LinkRiskToRequirementCommand(
                        command_id=request.command_id,
                        idempotency_key=request.idempotency_key,
                        correlation_id=request.correlation_id,
                        link_id=request.link_id,
                        case_id=case_id,
                        risk_id=risk_id,
                        requirement_id=request.requirement_id,
                        dce_version_id=request.dce_version_id,
                        relationship=request.relationship,
                        rationale=request.rationale,
                    ),
                    now=datetime.now(tz=UTC),
                )
            except PermissionError as error:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
                ) from error
            except (IdempotencyKeyReusedError, CommandInProgressError) as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="IDEMPOTENCY_CONFLICT"
                ) from error
            except CommandExecutionError as error:
                detail = str(error)
                code = (
                    status.HTTP_409_CONFLICT
                    if detail == "RISK_REQUIREMENT_LINK_ALREADY_EXISTS"
                    else status.HTTP_422_UNPROCESSABLE_CONTENT
                )
                raise HTTPException(status_code=code, detail=detail) from error
            reference = result.aggregate_refs[0]
            response = RiskRequirementLinkCommandResponse(
                command_id=result.command_id,
                idempotency_key=result.idempotency_key,
                result_code=result.result_code,
                link_id=UUID(str(reference["aggregate_id"])),
                version=int(reference["aggregate_revision"]),
                event_ids=[UUID(event_id) for event_id in result.event_ids],
                replayed=result.replayed,
            )
            return JSONResponse(
                status_code=200 if result.replayed else 201,
                content=response.model_dump(mode="json"),
            )

    if finalization_service is not None:

        @router.post(
            "/cases/{case_id}/decisions/{decision_id}/go-no-go",
            response_model=FinalizeGoNoGoDecisionResponse,
        )
        def finalize_go_no_go(
            case_id: UUID,
            decision_id: UUID,
            request: FinalizeGoNoGoDecisionRequest,
            authorization: str | None = Header(default=None),
        ):
            actor = _resolve_context(
                authorization=authorization,
                context_resolver=security_runtime.context_resolver,
            )
            try:
                result = finalization_service.execute(
                    actor=actor,
                    command=FinalizeGoNoGoDecisionCommand(
                        command_id=request.command_id,
                        idempotency_key=request.idempotency_key,
                        correlation_id=request.correlation_id,
                        decision_id=decision_id,
                        case_id=case_id,
                        expected_revision=request.expected_revision,
                        displayed_fingerprint=request.displayed_fingerprint,
                        outcome=request.outcome,
                        justification=request.justification,
                    ),
                    now=datetime.now(tz=UTC),
                )
            except PermissionError as error:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
                ) from error
            except (IdempotencyKeyReusedError, CommandInProgressError) as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="IDEMPOTENCY_CONFLICT"
                ) from error
            except CommandExecutionError as error:
                detail = str(error)
                if detail == "NOT_FOUND_OR_FORBIDDEN":
                    code = status.HTTP_404_NOT_FOUND
                elif detail in {"STALE_DECISION_CONTEXT", "STALE_DECISION_REVISION"}:
                    code = status.HTTP_409_CONFLICT
                else:
                    code = status.HTTP_422_UNPROCESSABLE_CONTENT
                raise HTTPException(status_code=code, detail=detail) from error
            reference = result.aggregate_refs[0]
            response = FinalizeGoNoGoDecisionResponse(
                command_id=result.command_id,
                idempotency_key=result.idempotency_key,
                result_code=result.result_code,
                decision_id=UUID(str(reference["aggregate_id"])),
                outcome=request.outcome,
                version=int(reference["aggregate_revision"]),
                event_ids=[UUID(event_id) for event_id in result.event_ids],
                replayed=result.replayed,
            )
            return JSONResponse(
                status_code=200,
                content=response.model_dump(mode="json"),
            )

    return router

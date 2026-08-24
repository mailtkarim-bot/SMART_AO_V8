from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.decision.application.patron_dossier import PatronDecisionDossierService
from app.modules.decision.application.risk import PatronDecisionRiskService
from app.modules.decision.application.risk_commands import RegisterStructuredRiskCommand
from app.modules.decision.public.patron_contracts import PatronDecisionDossierResponse
from app.modules.decision.public.risk_contracts import (
    RegisterStructuredRiskRequest,
    StructuredRiskCommandResponse,
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

    return router

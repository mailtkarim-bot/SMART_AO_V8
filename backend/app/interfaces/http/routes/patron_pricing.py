from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.pricing.application.commands import CreatePricingScenarioCommand
from app.modules.pricing.application.service import PricingScenarioService
from app.modules.pricing.public.contracts import (
    CreatePricingScenarioRequest,
    PricingScenarioCommandResponse,
    PricingScenarioResponse,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)


def build_patron_pricing_router(
    *, service: PricingScenarioService, security_runtime: ConsultationSecurityRuntime
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron", tags=["patron-pricing"])

    @router.get(
        "/cases/{case_id}/pricing-scenarios",
        response_model=list[PricingScenarioResponse],
    )
    def list_scenarios(
        case_id: UUID, authorization: str | None = Header(default=None)
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            scenarios = service.list_for_case(
                actor=actor, case_id=case_id, now=datetime.now(tz=UTC)
            )
        except PermissionError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
            ) from error
        return [PricingScenarioResponse(**asdict(item)) for item in scenarios]

    @router.post(
        "/cases/{case_id}/pricing-scenarios",
        response_model=PricingScenarioCommandResponse,
    )
    def create_scenario(
        case_id: UUID,
        request: CreatePricingScenarioRequest,
        authorization: str | None = Header(default=None),
    ):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            result = service.execute(
                actor=actor,
                command=CreatePricingScenarioCommand(
                    command_id=request.command_id,
                    idempotency_key=request.idempotency_key,
                    correlation_id=request.correlation_id,
                    scenario_id=request.scenario_id,
                    case_id=case_id,
                    source_snapshot_id=request.source_snapshot_id,
                    scenario_key=request.scenario_key,
                    scenario_type=request.scenario_type,
                    sales_adjustment_bps=request.sales_adjustment_bps,
                    cost_adjustment_bps=request.cost_adjustment_bps,
                    assumptions=request.assumptions,
                ),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
            ) from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(error)
            ) from error
        except CommandExecutionError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error
        reference = result.aggregate_refs[0]
        response = PricingScenarioCommandResponse(
            command_id=result.command_id,
            idempotency_key=result.idempotency_key,
            result_code=result.result_code,
            scenario_id=UUID(str(reference["aggregate_id"])),
            version=int(reference["aggregate_revision"]),
            event_ids=[UUID(event_id) for event_id in result.event_ids],
            replayed=result.replayed,
        )
        return JSONResponse(
            status_code=200 if result.replayed else 201,
            content=response.model_dump(mode="json"),
        )

    return router

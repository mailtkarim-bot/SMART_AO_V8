from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.preparation.application.transmission import PreparationTransmissionService
from app.modules.preparation.application.transmission_commands import (
    CreatePreparationSnapshotCommand,
    TransmitPreparationSnapshotCommand,
)
from app.modules.preparation.public.contracts import (
    CreatePreparationSnapshotRequest,
    PreparationAggregateReference,
    PreparationCommandResponse,
    TransmitPreparationSnapshotRequest,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)


def build_preparation_transmission_router(
    *, service: PreparationTransmissionService, security_runtime: ConsultationSecurityRuntime
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/collaborator", tags=["preparation-transmission"])

    @router.post(
        "/preparation/{package_id}/snapshots",
        status_code=status.HTTP_201_CREATED,
        response_model=PreparationCommandResponse,
    )
    def create_snapshot(
        package_id: UUID,
        request: CreatePreparationSnapshotRequest,
        authorization: str | None = Header(default=None),
    ):
        if request.package_id != package_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="PREPARATION_CONTEXT_MISMATCH",
            )
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service=service,
            actor=actor,
            command=CreatePreparationSnapshotCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                package_id=package_id,
                snapshot_id=request.snapshot_id,
                expected_package_revision=request.expected_package_revision,
            ),
        )

    @router.post(
        "/preparation/{package_id}/transmissions",
        status_code=status.HTTP_201_CREATED,
        response_model=PreparationCommandResponse,
    )
    def transmit_snapshot(
        package_id: UUID,
        request: TransmitPreparationSnapshotRequest,
        authorization: str | None = Header(default=None),
    ):
        if request.package_id != package_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="PREPARATION_CONTEXT_MISMATCH",
            )
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        return _dispatch(
            service=service,
            actor=actor,
            command=TransmitPreparationSnapshotCommand(
                command_id=request.command_id,
                idempotency_key=request.idempotency_key,
                correlation_id=request.correlation_id,
                package_id=package_id,
                snapshot_id=request.snapshot_id,
                transmission_id=request.transmission_id,
                expected_package_revision=request.expected_package_revision,
            ),
        )

    return router


def _dispatch(*, service: PreparationTransmissionService, actor, command):
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
            if detail in {"VERSION_CONFLICT", "SNAPSHOT_ALREADY_TRANSMITTED"}
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

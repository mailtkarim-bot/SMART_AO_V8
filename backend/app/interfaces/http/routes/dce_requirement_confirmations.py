"""SEC-01 guarded HTTP transport for human DCE requirement confirmation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.dce.application.requirement_confirmation import (
    DceRequirementConfirmationService,
    RequirementCaseScopeError,
)
from app.modules.dce.public.contracts import (
    RecordDceRequirementConfirmationRequest,
    RecordDceRequirementConfirmationResponse,
)
from app.platform.events.dispatcher import CommandExecutionError, IdempotencyKeyReusedError


def build_dce_requirement_confirmation_router(
    *,
    service: DceRequirementConfirmationService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    """Build the authenticated, server-scoped DCE requirement confirmation route."""

    router = APIRouter(prefix="/api/v1/dce-requirements", tags=["dce-requirements"])

    @router.post(
        "/{requirement_id}/confirmations",
        status_code=status.HTTP_201_CREATED,
        response_model=RecordDceRequirementConfirmationResponse,
    )
    def record_confirmation(
        requirement_id: UUID,
        request: RecordDceRequirementConfirmationRequest,
        authorization: str | None = Header(default=None),
    ) -> RecordDceRequirementConfirmationResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        command = request.to_command(requirement_id=requirement_id)
        try:
            result = service.confirm(
                actor=context,
                command=command,
                now=datetime.now(tz=UTC),
            )
        except RequirementCaseScopeError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="COMMAND_REJECTED",
            ) from error
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="NOT_FOUND_OR_FORBIDDEN",
                ) from error
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="FORBIDDEN",
            ) from error
        except IdempotencyKeyReusedError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="IDEMPOTENCY_KEY_REUSED",
            ) from error
        except CommandExecutionError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="COMMAND_REJECTED",
            ) from error

        response = RecordDceRequirementConfirmationResponse(
            command_id=result.command_id,
            idempotency_key=result.idempotency_key,
            result_code=result.result_code,
            aggregate_refs=list(result.aggregate_refs),
            event_ids=list(result.event_ids),
            replayed=result.replayed,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED,
            content=response.model_dump(mode="json"),
        )

    return router

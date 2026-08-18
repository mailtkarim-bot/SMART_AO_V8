from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.enterprise.application.enterprise_capability import EnterpriseCapabilityService
from app.modules.enterprise.public.enterprise_capability_contracts import (
    AddEnterpriseCapabilityVersionRequest,
    CreateEnterpriseCapabilityRequest,
    EnterpriseCapabilityListResponse,
    EnterpriseCapabilityReceiptResponse,
    EnterpriseCapabilityResponse,
    EnterpriseCapabilityVersionResponse,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)


def _receipt(result) -> EnterpriseCapabilityReceiptResponse:
    return EnterpriseCapabilityReceiptResponse(
        status="SUCCEEDED",
        command_id=result.command_id,
        idempotency_key=result.idempotency_key,
        result_code=result.result_code,
        aggregate_refs=list(result.aggregate_refs),
        event_ids=list(result.event_ids),
        replayed=result.replayed,
    )


def _capability_response(projection) -> EnterpriseCapabilityResponse:
    return EnterpriseCapabilityResponse(
        capability_id=projection.capability_id,
        company_id=projection.company_id,
        aggregate_revision=projection.aggregate_revision,
        capability_kind=projection.capability_kind,
        name=projection.name,
        summary=projection.summary,
        state=projection.state,
        versions=[
            EnterpriseCapabilityVersionResponse(
                version_id=version.version_id,
                version_number=version.version_number,
                title=version.title,
                description=version.description,
                valid_from=version.valid_from,
                valid_until=version.valid_until,
                usage_scope=version.usage_scope,
                proof_document_ids=list(version.proof_document_ids),
            )
            for version in projection.versions
        ],
    )


def build_patron_enterprise_capability_router(
    *,
    service: EnterpriseCapabilityService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron/enterprise", tags=["patron-enterprise-capabilities"])

    @router.post(
        "/companies/{company_id}/capabilities",
        status_code=status.HTTP_201_CREATED,
        response_model=EnterpriseCapabilityReceiptResponse,
        responses={
            200: {"description": "Rejeu idempotent de la création."},
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Capability réservée au patron."},
            404: {"description": "Société absente ou hors tenant."},
            409: {"description": "Conflit d’idempotence ou capacité existante."},
            422: {"description": "Invariant de capacité refusé."},
        },
    )
    def create_capability(
        company_id: UUID,
        request: CreateEnterpriseCapabilityRequest,
        authorization: str | None = Header(default=None),
    ) -> EnterpriseCapabilityReceiptResponse:
        context = _resolve_context(
            authorization=authorization, context_resolver=security_runtime.context_resolver
        )
        try:
            result = service.create_capability(
                actor=context,
                command=request.to_command(company_id=company_id),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
        except CommandExecutionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            if str(error) == "CAPABILITY_ALREADY_EXISTS":
                raise HTTPException(status_code=409, detail="CAPABILITY_ALREADY_EXISTS") from error
            raise HTTPException(status_code=422, detail="COMMAND_REJECTED") from error
        receipt = _receipt(result)
        return JSONResponse(
            status_code=200 if result.replayed else 201,
            content=receipt.model_dump(mode="json"),
        )

    @router.post(
        "/capabilities/{capability_id}/versions",
        status_code=status.HTTP_201_CREATED,
        response_model=EnterpriseCapabilityReceiptResponse,
        responses={
            200: {"description": "Rejeu idempotent du versionnement."},
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Capability réservée au patron."},
            404: {"description": "Capacité ou preuve absente du tenant."},
            409: {"description": "Conflit d’idempotence ou de révision."},
            422: {"description": "Invariant de version ou de preuve refusé."},
        },
    )
    def add_version(
        capability_id: UUID,
        request: AddEnterpriseCapabilityVersionRequest,
        authorization: str | None = Header(default=None),
    ) -> EnterpriseCapabilityReceiptResponse:
        context = _resolve_context(
            authorization=authorization, context_resolver=security_runtime.context_resolver
        )
        try:
            result = service.add_version(
                actor=context,
                command=request.to_command(capability_id=capability_id),
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        except (IdempotencyKeyReusedError, CommandInProgressError) as error:
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT") from error
        except CommandExecutionError as error:
            if str(error) in {"NOT_FOUND_OR_FORBIDDEN", "PROOF_NOT_FOUND_OR_FORBIDDEN"}:
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            if str(error) == "VERSION_CONFLICT":
                raise HTTPException(status_code=409, detail="VERSION_CONFLICT") from error
            if str(error) == "CAPABILITY_VERSION_ALREADY_EXISTS":
                raise HTTPException(
                    status_code=409, detail="CAPABILITY_VERSION_ALREADY_EXISTS"
                ) from error
            raise HTTPException(status_code=422, detail="COMMAND_REJECTED") from error
        receipt = _receipt(result)
        return JSONResponse(
            status_code=200 if result.replayed else 201,
            content=receipt.model_dump(mode="json"),
        )

    @router.get(
        "/companies/{company_id}/capabilities",
        response_model=EnterpriseCapabilityListResponse,
        responses={
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Capability réservée au patron."},
            404: {"description": "Société absente ou hors tenant."},
        },
    )
    def read_capabilities(
        company_id: UUID,
        authorization: str | None = Header(default=None),
    ) -> EnterpriseCapabilityListResponse:
        context = _resolve_context(
            authorization=authorization, context_resolver=security_runtime.context_resolver
        )
        try:
            projections = service.read_capabilities(
                actor=context,
                company_id=company_id,
                now=datetime.now(tz=UTC),
            )
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(status_code=404, detail="NOT_FOUND_OR_FORBIDDEN") from error
            raise HTTPException(status_code=403, detail="FORBIDDEN") from error
        return EnterpriseCapabilityListResponse(
            capabilities=[_capability_response(item) for item in projections]
        )

    return router

"""Authenticated transport for read-only INSEE Sirene verification."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Path, status

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.enterprise.application.registry_lookup import EnterpriseRegistryLookupService
from app.modules.enterprise.infrastructure.insee_registry import ExternalRegistryUnavailable
from app.modules.enterprise.public.enterprise_registry_contracts import EnterpriseRegistryResponse
from app.platform.security.authorization import AuthorizationRequest, AuthorizationResource
from app.platform.security.capabilities import Capability
from app.platform.security.context import DataClassification


def build_patron_enterprise_registry_router(
    *,
    service: EnterpriseRegistryLookupService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron/enterprise", tags=["patron-enterprise-registry"])

    @router.get(
        "/registry/{siren}",
        response_model=EnterpriseRegistryResponse,
        responses={
            401: {"description": "Bearer absent, invalide ou expiré."},
            403: {"description": "Vérification registre réservée au patron."},
            404: {"description": "SIREN absent du registre."},
            422: {"description": "SIREN invalide."},
            503: {"description": "Registre externe indisponible."},
        },
    )
    def lookup_company(
        siren: str = Path(min_length=9, max_length=9, pattern=r"^\d{9}$"),
        authorization: str | None = Header(default=None),
    ) -> EnterpriseRegistryResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        decision = security_runtime.policy.authorize(
            context=context,
            request=AuthorizationRequest(
                action=Capability.ENTERPRISE_REGISTRY_READ,
                resource=AuthorizationResource(
                    resource_type="PUBLIC_ENTERPRISE_REGISTRY",
                    resource_id=context.tenant_id,
                    tenant_id=context.tenant_id,
                    classification=DataClassification.PUBLIC_TENDER,
                ),
                evaluated_at=datetime.now(tz=UTC),
            ),
        )
        if not decision.allowed:
            if decision.http_status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="NOT_FOUND_OR_FORBIDDEN",
                )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")
        try:
            company = service.find_by_siren(siren=siren)
        except ExternalRegistryUnavailable:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="EXTERNAL_REGISTRY_UNAVAILABLE",
            ) from None
        except RuntimeError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="EXTERNAL_REGISTRY_UNAVAILABLE",
            ) from None
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="SIREN_INVALID",
            ) from None
        if company is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SIREN_NOT_FOUND")
        return EnterpriseRegistryResponse(
            siren=company.siren,
            legal_name=company.legal_name,
            active=company.active,
            activity_code=company.activity_code,
            source=company.source,
        )

    return router

"""Authenticated HTTP transport for public procurement watch."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.market_watch.application.service import PublicNoticeSearchService
from app.modules.market_watch.infrastructure.boamp import BoampRegistryUnavailable
from app.modules.market_watch.public.contracts import (
    PublicNoticeContract,
    PublicNoticeSearchResponse,
)
from app.platform.security.authorization import AuthorizationRequest, AuthorizationResource
from app.platform.security.capabilities import Capability
from app.platform.security.context import DataClassification


def build_market_watch_router(
    *,
    service: PublicNoticeSearchService,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/market-watch", tags=["market-watch"])

    @router.get("/boamp/search", response_model=PublicNoticeSearchResponse)
    def search_boamp(
        q: str = Query(min_length=1, max_length=200),
        limit: int = Query(default=20, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10_000),
        authorization: str | None = Header(default=None),
    ) -> PublicNoticeSearchResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        decision = security_runtime.policy.authorize(
            context=context,
            request=AuthorizationRequest(
                action=Capability.MARKET_WATCH_READ,
                resource=AuthorizationResource(
                    resource_type="PUBLIC_MARKET_WATCH",
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
            notices = service.search(text=q, limit=limit, offset=offset)
        except (BoampRegistryUnavailable, RuntimeError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PUBLIC_NOTICE_SOURCE_UNAVAILABLE",
            ) from None
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="PUBLIC_NOTICE_QUERY_INVALID",
            ) from None
        return PublicNoticeSearchResponse(
            query=q,
            limit=limit,
            offset=offset,
            results=[
                PublicNoticeContract(
                    notice_id=notice.notice_id,
                    title=notice.title,
                    publication_date=notice.publication_date,
                    response_deadline=notice.response_deadline,
                    department_codes=notice.department_codes,
                    market_types=notice.market_types,
                    status=notice.status,
                )
                for notice in notices
            ],
        )

    return router

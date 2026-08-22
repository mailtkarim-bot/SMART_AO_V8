"""Authenticated HTTP transport for case-scoped local retrieval."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_versions import _resolve_context
from app.modules.knowledge.application.service import KnowledgeRetrievalService
from app.modules.knowledge.public.contracts import KnowledgeSearchResponse, KnowledgeSearchResult
from app.platform.security.authorization import AuthorizationRequest, AuthorizationResource
from app.platform.security.capabilities import Capability
from app.platform.security.context import DataClassification


def build_knowledge_router(
    *,
    service: KnowledgeRetrievalService,
    runtime,
    security_runtime: ConsultationSecurityRuntime,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/cases", tags=["knowledge"])

    @router.get("/{case_id}/knowledge/search", response_model=KnowledgeSearchResponse)
    def search_case_knowledge(
        case_id: UUID,
        q: str = Query(min_length=1, max_length=500),
        top_k: int = Query(default=5, ge=1, le=10),
        authorization: str | None = Header(default=None),
    ) -> KnowledgeSearchResponse:
        context = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        owner_tenant_id = runtime.get_case_tenant_id(case_id=case_id)
        if owner_tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NOT_FOUND_OR_FORBIDDEN",
            )
        decision = security_runtime.policy.authorize(
            context=context,
            request=AuthorizationRequest(
                action=Capability.CASE_DCE_READ,
                resource=AuthorizationResource(
                    resource_type="CASE_KNOWLEDGE_RETRIEVAL",
                    resource_id=case_id,
                    tenant_id=owner_tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=case_id,
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
            results = service.search_case_dce(
                tenant_id=context.tenant_id,
                case_id=case_id,
                query=q,
                top_k=top_k,
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="KNOWLEDGE_RETRIEVAL_UNAVAILABLE",
            ) from exc
        return KnowledgeSearchResponse(
            case_id=case_id,
            query=q,
            results=[
                KnowledgeSearchResult(
                    source_fragment_id=result.chunk.source_fragment_id,
                    dce_version_id=result.chunk.dce_version_id,
                    score=result.score,
                    excerpt=result.chunk.text[:1_000],
                    locator=result.chunk.locator,
                    embedding_model=result.embedding_model,
                )
                for result in results
            ],
        )

    return router

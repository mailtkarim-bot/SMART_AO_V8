from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from app.interfaces.http.routes import knowledge as knowledge_route
from app.interfaces.http.routes.knowledge import build_knowledge_router
from app.modules.dce.application.queries import CaseDceReadingAvailability
from app.modules.knowledge.domain.retrieval import (
    DataClassification,
    RetrievalChunk,
    RetrievalResult,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CASE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001")
VERSION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002")
FRAGMENT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0003")


class FakeKnowledgeService:
    def search_case_dce(self, *, tenant_id, case_id, dce_version_id, query, top_k):
        assert tenant_id == TENANT_ID
        assert case_id == CASE_ID
        assert dce_version_id == VERSION_ID
        assert query == "délai"
        assert top_k == 3
        return [
            RetrievalResult(
                chunk=RetrievalChunk(
                    chunk_id=FRAGMENT_ID,
                    tenant_id=TENANT_ID,
                    case_id=CASE_ID,
                    dce_version_id=VERSION_ID,
                    source_fragment_id=FRAGMENT_ID,
                    ordinal=1,
                    text="Le délai de réponse est fixé à dix jours.",
                    locator={"page": 4},
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                ),
                score=0.91,
                embedding_model="fake-bge-m3",
            )
        ]


class FakePolicy:
    def __init__(self) -> None:
        self.requests = []

    def authorize(self, *, context, request):
        self.requests.append(request)
        return SimpleNamespace(allowed=True, http_status_code=200)


class FakeRuntime:
    def get_case_tenant_id(self, *, case_id):
        assert case_id == CASE_ID
        return TENANT_ID

    def get_case_dce_reading(self, *, tenant_id, case_id):
        assert tenant_id == TENANT_ID
        assert case_id == CASE_ID
        return SimpleNamespace(
            availability=CaseDceReadingAvailability.AVAILABLE,
            reading=SimpleNamespace(dce_version_id=VERSION_ID),
        )


def test_knowledge_search_returns_bounded_source_citation(monkeypatch) -> None:
    monkeypatch.setattr(
        knowledge_route,
        "_resolve_context",
        lambda *, authorization, context_resolver: SimpleNamespace(tenant_id=TENANT_ID),
    )
    policy = FakePolicy()
    security_runtime = SimpleNamespace(context_resolver=object(), policy=policy)
    app = FastAPI()
    app.include_router(
        build_knowledge_router(
            service=FakeKnowledgeService(),
            runtime=FakeRuntime(),
            security_runtime=security_runtime,
        )
    )

    response = TestClient(app, base_url="https://smart-ao.test").get(
        f"/api/v1/cases/{CASE_ID}/knowledge/search",
        params={"q": "délai", "top_k": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["case_id"] == str(CASE_ID)
    assert payload["results"][0] == {
        "source_fragment_id": str(FRAGMENT_ID),
        "dce_version_id": str(VERSION_ID),
        "score": 0.91,
        "locator": {"page": 4},
        "embedding_model": "fake-bge-m3",
    }
    assert "storage_key" not in payload["results"][0]
    assert "excerpt" not in payload["results"][0]
    assert "text" not in payload["results"][0]
    assert policy.requests[0].resource.tenant_id == TENANT_ID


def test_knowledge_search_rejects_invalid_top_k(monkeypatch) -> None:
    monkeypatch.setattr(
        knowledge_route,
        "_resolve_context",
        lambda *, authorization, context_resolver: SimpleNamespace(tenant_id=TENANT_ID),
    )
    app = FastAPI()
    app.include_router(
        build_knowledge_router(
            service=FakeKnowledgeService(),
            runtime=FakeRuntime(),
            security_runtime=SimpleNamespace(
                context_resolver=object(),
                policy=FakePolicy(),
            ),
        )
    )

    response = TestClient(app).get(
        f"/api/v1/cases/{CASE_ID}/knowledge/search",
        params={"q": "délai", "top_k": 11},
    )

    assert response.status_code == 422

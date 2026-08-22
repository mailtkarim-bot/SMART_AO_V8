from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
from app.modules.knowledge.application.retrieval import (
    InMemoryVectorIndex,
    RagRetrievalService,
)
from app.modules.knowledge.domain.retrieval import (
    DataClassification,
    RetrievalChunk,
    RetrievalScope,
)

TENANT_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
CASE_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001")
CASE_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbb0001")


@dataclass
class FakeEmbeddingProvider:
    vectors: dict[str, tuple[float, ...]]
    model_id: str = "fake-bge-m3"

    def embed(self, texts: list[str]) -> list[tuple[float, ...]]:
        return [self.vectors[text] for text in texts]


@pytest.fixture
def retrieval_service() -> RagRetrievalService:
    provider = FakeEmbeddingProvider(
        vectors={
            "pénalité de retard": (1.0, 0.0),
            "délai de chantier": (0.9, 0.1),
            "prix interne confidentiel": (0.0, 1.0),
            "autre affaire": (1.0, 0.0),
        }
    )
    return RagRetrievalService(
        embedding_provider=provider,
        index=InMemoryVectorIndex(),
    )


def _chunk(
    *,
    chunk_id: str,
    tenant_id: UUID,
    case_id: UUID,
    text: str,
    classification: DataClassification = DataClassification.INTERNAL_OPERATIONAL,
) -> RetrievalChunk:
    return RetrievalChunk(
        chunk_id=UUID(chunk_id),
        tenant_id=tenant_id,
        case_id=case_id,
        source_fragment_id=UUID(chunk_id),
        ordinal=1,
        text=text,
        locator={"page": 1},
        classification=classification,
    )


def test_retrieval_is_tenant_and_case_scoped(retrieval_service: RagRetrievalService) -> None:
    retrieval_service.index(
        chunks=[
            _chunk(
                chunk_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0101",
                tenant_id=TENANT_A,
                case_id=CASE_A,
                text="pénalité de retard",
            ),
            _chunk(
                chunk_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbb0101",
                tenant_id=TENANT_B,
                case_id=CASE_B,
                text="autre affaire",
            ),
        ]
    )

    results = retrieval_service.retrieve(
        query="pénalité de retard",
        scope=RetrievalScope(tenant_id=TENANT_A, case_id=CASE_A),
        top_k=5,
    )

    assert [result.chunk.chunk_id for result in results] == [
        UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0101")
    ]
    assert all(result.chunk.tenant_id == TENANT_A for result in results)
    assert all(result.chunk.case_id == CASE_A for result in results)


def test_retrieval_excludes_financial_private_chunks_by_default(
    retrieval_service: RagRetrievalService,
) -> None:
    retrieval_service.index(
        chunks=[
            _chunk(
                chunk_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0102",
                tenant_id=TENANT_A,
                case_id=CASE_A,
                text="prix interne confidentiel",
                classification=DataClassification.FINANCIAL_PRIVATE,
            ),
            _chunk(
                chunk_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0103",
                tenant_id=TENANT_A,
                case_id=CASE_A,
                text="pénalité de retard",
            ),
        ]
    )

    results = retrieval_service.retrieve(
        query="prix interne confidentiel",
        scope=RetrievalScope(tenant_id=TENANT_A, case_id=CASE_A),
        top_k=5,
    )

    assert results == []


def test_retrieval_requires_positive_bounded_top_k(
    retrieval_service: RagRetrievalService,
) -> None:
    with pytest.raises(ValueError, match="top_k"):
        retrieval_service.retrieve(
            query="pénalité de retard",
            scope=RetrievalScope(tenant_id=TENANT_A, case_id=CASE_A),
            top_k=0,
        )

    with pytest.raises(ValueError, match="top_k"):
        retrieval_service.retrieve(
            query="pénalité de retard",
            scope=RetrievalScope(tenant_id=TENANT_A, case_id=CASE_A),
            top_k=51,
        )


def test_retrieval_preserves_provenance_and_score(
    retrieval_service: RagRetrievalService,
) -> None:
    retrieval_service.index(
        chunks=[
            _chunk(
                chunk_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0104",
                tenant_id=TENANT_A,
                case_id=CASE_A,
                text="délai de chantier",
            )
        ]
    )

    [result] = retrieval_service.retrieve(
        query="pénalité de retard",
        scope=RetrievalScope(tenant_id=TENANT_A, case_id=CASE_A),
        top_k=1,
    )

    assert result.chunk.source_fragment_id == result.chunk.chunk_id
    assert result.chunk.locator == {"page": 1}
    assert 0.0 <= result.score <= 1.0
    assert result.embedding_model == "fake-bge-m3"

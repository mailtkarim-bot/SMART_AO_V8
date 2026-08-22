from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.knowledge.application.retrieval import InMemoryVectorIndex, RagRetrievalService
from app.modules.knowledge.application.service import KnowledgeRetrievalService
from app.modules.knowledge.domain.retrieval import DataClassification, RetrievalChunk

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CASE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001")
VERSION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002")
FRAGMENT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0003")


@dataclass
class FakeProvider:
    model_id: str = "fake-bge-m3"

    def embed(self, texts: list[str]) -> list[tuple[float, ...]]:
        return [(1.0, 0.0) for _ in texts]


class FakeSource:
    def __init__(self, chunks: tuple[RetrievalChunk, ...]) -> None:
        self.chunks = chunks
        self.calls: list[dict[str, UUID]] = []

    def read_chunks(self, *, tenant_id: UUID, case_id: UUID, dce_version_id: UUID):
        self.calls.append(
            {
                "tenant_id": tenant_id,
                "case_id": case_id,
                "dce_version_id": dce_version_id,
            }
        )
        return self.chunks


def test_knowledge_service_indexes_and_searches_through_ports() -> None:
    chunk = RetrievalChunk(
        chunk_id=FRAGMENT_ID,
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        dce_version_id=VERSION_ID,
        source_fragment_id=FRAGMENT_ID,
        ordinal=1,
        text="délai de réponse",
        locator={"page": 3},
        classification=DataClassification.INTERNAL_OPERATIONAL,
    )
    source = FakeSource((chunk,))
    service = KnowledgeRetrievalService(
        retrieval=RagRetrievalService(
            embedding_provider=FakeProvider(),
            index=InMemoryVectorIndex(),
        ),
        source=source,
    )

    assert service.index_case_dce(
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        dce_version_id=VERSION_ID,
    ) == 1
    results = service.search_case_dce(
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        query="délai",
        top_k=1,
    )

    assert source.calls == [
        {
            "tenant_id": TENANT_ID,
            "case_id": CASE_ID,
            "dce_version_id": VERSION_ID,
        }
    ]
    assert len(results) == 1
    assert results[0].chunk.source_fragment_id == FRAGMENT_ID

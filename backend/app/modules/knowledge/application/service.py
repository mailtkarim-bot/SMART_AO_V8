from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.modules.knowledge.application.retrieval import RagRetrievalService
from app.modules.knowledge.domain.retrieval import RetrievalChunk, RetrievalResult, RetrievalScope


class DceRetrievalSource(Protocol):
    def read_chunks(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        dce_version_id: UUID,
    ) -> Sequence[RetrievalChunk]: ...


class KnowledgeRetrievalService:
    def __init__(
        self,
        *,
        retrieval: RagRetrievalService,
        source: DceRetrievalSource,
    ) -> None:
        self._retrieval = retrieval
        self._source = source

    def index_case_dce(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        dce_version_id: UUID,
    ) -> int:
        chunks = self._source.read_chunks(
            tenant_id=tenant_id,
            case_id=case_id,
            dce_version_id=dce_version_id,
        )
        self._retrieval.index(chunks=chunks)
        return len(chunks)

    def search_case_dce(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        query: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        return self._retrieval.retrieve(
            query=query,
            scope=RetrievalScope(tenant_id=tenant_id, case_id=case_id),
            top_k=top_k,
        )

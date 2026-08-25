from __future__ import annotations

from collections.abc import Sequence
from math import sqrt
from typing import Protocol

from app.modules.knowledge.domain.retrieval import (
    MAX_TOP_K,
    DataClassification,
    EmbeddingVector,
    RetrievalChunk,
    RetrievalResult,
    RetrievalScope,
)


class EmbeddingProvider(Protocol):
    @property
    def model_id(self) -> str: ...

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]: ...


class VectorIndex(Protocol):
    def upsert(
        self,
        *,
        chunks: Sequence[RetrievalChunk],
        embeddings: Sequence[EmbeddingVector],
    ) -> None: ...

    def search(
        self,
        *,
        query: EmbeddingVector,
        scope: RetrievalScope,
        top_k: int,
        embedding_model: str,
    ) -> list[RetrievalResult]: ...


class InMemoryVectorIndex:
    """Small deterministic index used by tests and local smoke runs.

    Production persistence is deliberately a separate adapter. Keeping this index
    free of SQLAlchemy allows the retrieval contract to be tested without a DB.
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[object, object], tuple[RetrievalChunk, EmbeddingVector]] = {}

    def upsert(
        self,
        *,
        chunks: Sequence[RetrievalChunk],
        embeddings: Sequence[EmbeddingVector],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            if chunk.classification is DataClassification.FINANCIAL_PRIVATE:
                continue
            self._entries[(chunk.tenant_id, chunk.chunk_id)] = (chunk, embedding)

    def search(
        self,
        *,
        query: EmbeddingVector,
        scope: RetrievalScope,
        top_k: int,
        embedding_model: str,
    ) -> list[RetrievalResult]:
        visible = (
            (chunk, embedding)
            for chunk, embedding in self._entries.values()
            if chunk.is_visible_in(scope)
        )
        scored = []
        for chunk, embedding in visible:
            if embedding.dimension != query.dimension:
                continue
            score = _cosine_similarity(query, embedding)
            if score <= 0.0:
                continue
            scored.append(
                RetrievalResult(
                    chunk=chunk,
                    score=score,
                    embedding_model=embedding_model,
                )
            )
        scored.sort(
            key=lambda result: (-result.score, result.chunk.ordinal, str(result.chunk.chunk_id))
        )
        return scored[:top_k]


class RagRetrievalService:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        index: VectorIndex,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._index = index

    def index(self, *, chunks: Sequence[RetrievalChunk]) -> None:
        if not chunks:
            return
        embeddings = [
            EmbeddingVector(values=values)
            for values in self._embedding_provider.embed([chunk.text for chunk in chunks])
        ]
        self._index.upsert(chunks=chunks, embeddings=embeddings)

    def retrieve(
        self,
        *,
        query: str,
        scope: RetrievalScope,
        top_k: int,
    ) -> list[RetrievalResult]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= top_k <= MAX_TOP_K:
            raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}")
        [query_embedding] = self._embedding_provider.embed([query])
        return self._index.search(
            query=EmbeddingVector(values=query_embedding),
            scope=scope,
            top_k=top_k,
            embedding_model=self._embedding_provider.model_id,
        )


def _cosine_similarity(left: EmbeddingVector, right: EmbeddingVector) -> float:
    if left.dimension != right.dimension:
        raise ValueError("embedding dimensions must match")
    left_norm = sqrt(sum(value * value for value in left.values))
    right_norm = sqrt(sum(value * value for value in right.values))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    similarity = sum(a * b for a, b in zip(left.values, right.values, strict=True)) / (
        left_norm * right_norm
    )
    return max(0.0, min(1.0, similarity))

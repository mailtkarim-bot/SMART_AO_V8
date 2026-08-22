from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.knowledge.application.retrieval import (
    InMemoryVectorIndex,
    VectorIndex,
)
from app.modules.knowledge.domain.retrieval import (
    DataClassification,
    EmbeddingVector,
    RetrievalChunk,
    RetrievalResult,
    RetrievalScope,
)
from app.modules.knowledge.infrastructure.models import DceFragmentEmbeddingRecord


class SqlAlchemyVectorIndex(VectorIndex):
    """Persistent index bridge until a measured pgvector migration is justified."""

    def __init__(self, *, session_factory: sessionmaker[Session], model_id: str) -> None:
        if not model_id.strip():
            raise ValueError("model_id must not be empty")
        self._session_factory = session_factory
        self._model_id = model_id

    def upsert(
        self,
        *,
        chunks: Sequence[RetrievalChunk],
        embeddings: Sequence[EmbeddingVector],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        with self._session_factory.begin() as session:
            for chunk, embedding in zip(chunks, embeddings, strict=True):
                if chunk.classification is DataClassification.FINANCIAL_PRIVATE:
                    continue
                source_hash = sha256(chunk.text.encode("utf-8")).hexdigest()
                existing = session.scalar(
                    sa.select(DceFragmentEmbeddingRecord).where(
                        DceFragmentEmbeddingRecord.tenant_id == chunk.tenant_id,
                        DceFragmentEmbeddingRecord.fragment_id == chunk.source_fragment_id,
                        DceFragmentEmbeddingRecord.model_id == self._model_id,
                    )
                )
                if existing is not None:
                    embedding_values = list(embedding.values)
                    if (
                        existing.text_sha256 != source_hash
                        or existing.embedding != embedding_values
                    ):
                        raise ValueError(
                            "embedding identity already exists with different content"
                        )
                    continue
                session.add(
                    DceFragmentEmbeddingRecord(
                        id=uuid4(),
                        tenant_id=chunk.tenant_id,
                        dce_version_id=chunk.dce_version_id,
                        case_id=chunk.case_id,
                        fragment_id=chunk.source_fragment_id,
                        model_id=self._model_id,
                        ordinal=chunk.ordinal,
                        text=chunk.text,
                        locator_json=chunk.locator,
                        classification=chunk.classification.value,
                        text_sha256=source_hash,
                        embedding=list(embedding.values),
                        embedding_dimension=embedding.dimension,
                    )
                )

    def search(
        self,
        *,
        query: EmbeddingVector,
        scope: RetrievalScope,
        top_k: int,
        embedding_model: str,
    ) -> list[RetrievalResult]:
        with self._session_factory() as session:
            rows = session.scalars(
                sa.select(DceFragmentEmbeddingRecord)
                .where(
                    DceFragmentEmbeddingRecord.tenant_id == scope.tenant_id,
                    DceFragmentEmbeddingRecord.case_id == scope.case_id,
                    DceFragmentEmbeddingRecord.model_id == embedding_model,
                    DceFragmentEmbeddingRecord.classification.in_(
                        classification.value for classification in scope.allowed_classifications
                    ),
                )
                .order_by(
                    DceFragmentEmbeddingRecord.ordinal,
                    DceFragmentEmbeddingRecord.id,
                )
            ).all()
        chunks = [
            RetrievalChunk(
                chunk_id=row.id,
                tenant_id=row.tenant_id,
                case_id=row.case_id,
                dce_version_id=row.dce_version_id,
                source_fragment_id=row.fragment_id,
                ordinal=row.ordinal,
                text=row.text,
                locator=row.locator_json,
                classification=DataClassification(row.classification),
            )
            for row in rows
        ]
        embeddings = [EmbeddingVector(values=tuple(row.embedding)) for row in rows]
        index = InMemoryVectorIndex()
        index.upsert(chunks=chunks, embeddings=embeddings)
        return index.search(
            query=query,
            scope=scope,
            top_k=top_k,
            embedding_model=embedding_model,
        )

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.modules.knowledge.application.retrieval import RagRetrievalService
from app.modules.knowledge.application.service import KnowledgeRetrievalService
from app.modules.knowledge.infrastructure.bge_embeddings import BgeEmbeddingProvider
from app.modules.knowledge.infrastructure.dce_source import SqlAlchemyDceRetrievalSource
from app.modules.knowledge.infrastructure.vector_index import SqlAlchemyVectorIndex


def build_local_knowledge_service(
    *,
    session_factory: sessionmaker[Session],
    model_id: str = "BAAI/bge-m3",
    cache_dir: Path = Path("/var/lib/smart_ao/models"),
    local_files_only: bool = True,
) -> KnowledgeRetrievalService:
    provider = BgeEmbeddingProvider(
        model_id=model_id,
        cache_dir=cache_dir,
        local_files_only=local_files_only,
    )
    return KnowledgeRetrievalService(
        retrieval=RagRetrievalService(
            embedding_provider=provider,
            index=SqlAlchemyVectorIndex(
                session_factory=session_factory,
                model_id=model_id,
            ),
        ),
        source=SqlAlchemyDceRetrievalSource(session_factory=session_factory),
    )

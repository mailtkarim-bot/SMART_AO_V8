from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from app.modules.knowledge.domain.retrieval import DataClassification, RetrievalScope
from app.modules.knowledge.infrastructure.vector_index import SqlAlchemyVectorIndex

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CASE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001")
VERSION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002")


class FakeSession:
    def __init__(self) -> None:
        self.statement = None

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def scalars(self, statement):
        self.statement = statement
        return SimpleNamespace(all=lambda: [])


class FakeSessionFactory:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def __call__(self) -> FakeSession:
        return self.session


def test_sqlalchemy_search_filters_the_applicable_dce_version() -> None:
    session = FakeSession()
    index = SqlAlchemyVectorIndex(
        session_factory=FakeSessionFactory(session),
        model_id="fake-bge-m3",
    )

    index.search(
        query=SimpleNamespace(dimension=2, values=(1.0, 0.0)),
        scope=RetrievalScope(
            tenant_id=TENANT_ID,
            case_id=CASE_ID,
            dce_version_id=VERSION_ID,
        ),
        top_k=5,
        embedding_model="fake-bge-m3",
    )

    compiled_statement = session.statement.compile()
    compiled = str(compiled_statement)
    params = {str(value) for value in compiled_statement.params.values()}
    assert "dce_fragment_embeddings.dce_version_id" in compiled
    assert str(VERSION_ID) in params
    assert "dce_fragment_embeddings.tenant_id" in compiled
    assert str(TENANT_ID) in params
    assert "dce_fragment_embeddings.case_id" in compiled
    assert str(CASE_ID) in params
    assert "FINANCIAL_PRIVATE" not in compiled
    assert DataClassification.FINANCIAL_PRIVATE.value not in compiled

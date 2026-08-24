from __future__ import annotations

import sys
from types import ModuleType

from app.modules.knowledge.infrastructure.bge_embeddings import BgeEmbeddingProvider


def test_bge_provider_loads_lazily_and_requests_local_cpu_model(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeSentenceTransformer:
        def __init__(self, model_id: str, **kwargs: object) -> None:
            calls.append({"model_id": model_id, **kwargs})
            self.max_seq_length = None

        def encode(self, texts: list[str], **kwargs: object) -> list[list[float]]:
            assert texts == ["exigence de délai"]
            assert kwargs["normalize_embeddings"] is True
            return [[3.0, 4.0]]

    fake_module = ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    provider = BgeEmbeddingProvider()
    assert calls == []

    vectors = provider.embed(["exigence de délai"])

    assert vectors == [(3.0, 4.0)]
    assert calls == [
        {
            "model_id": "BAAI/bge-m3",
            "device": "cpu",
            "local_files_only": True,
        }
    ]
    assert provider.embed([]) == []


def test_bge_provider_rejects_blank_text() -> None:
    provider = BgeEmbeddingProvider()

    try:
        provider.embed(["  "])
    except ValueError as exc:
        assert str(exc) == "embedding text must not be empty"
    else:
        raise AssertionError("blank text should be rejected")

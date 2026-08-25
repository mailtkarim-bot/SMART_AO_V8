from __future__ import annotations

import pytest
from app.workers import knowledge_embeddings


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " On "])
def test_env_flag_accepts_true_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("SMART_AO_TEST_FLAG", value)

    assert knowledge_embeddings._env_flag("SMART_AO_TEST_FLAG", default=False) is True


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off", " Off "])
def test_env_flag_accepts_false_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("SMART_AO_TEST_FLAG", value)

    assert knowledge_embeddings._env_flag("SMART_AO_TEST_FLAG", default=True) is False


def test_env_flag_rejects_ambiguous_values(monkeypatch) -> None:
    monkeypatch.setenv("SMART_AO_TEST_FLAG", "maybe")

    with pytest.raises(SystemExit, match="must be a boolean flag"):
        knowledge_embeddings._env_flag("SMART_AO_TEST_FLAG", default=False)


def test_rag_indexing_requires_read_runtime_flag(monkeypatch) -> None:
    monkeypatch.setenv("SMART_AO_RAG_ENABLED", "0")
    monkeypatch.setenv("SMART_AO_RAG_INDEXING_ENABLED", "1")

    with pytest.raises(SystemExit, match="SMART_AO_RAG_ENABLED"):
        knowledge_embeddings._require_indexing_enabled()


def test_rag_indexing_requires_separate_explicit_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("SMART_AO_RAG_ENABLED", "1")
    monkeypatch.setenv("SMART_AO_RAG_INDEXING_ENABLED", "0")

    with pytest.raises(SystemExit, match="SMART_AO_RAG_INDEXING_ENABLED"):
        knowledge_embeddings._require_indexing_enabled()


def test_rag_indexing_is_disabled_when_flags_are_absent(monkeypatch) -> None:
    monkeypatch.delenv("SMART_AO_RAG_ENABLED", raising=False)
    monkeypatch.delenv("SMART_AO_RAG_INDEXING_ENABLED", raising=False)

    with pytest.raises(SystemExit, match="SMART_AO_RAG_ENABLED"):
        knowledge_embeddings._require_indexing_enabled()


def test_rag_indexing_accepts_explicit_true_flags(monkeypatch) -> None:
    monkeypatch.setenv("SMART_AO_RAG_ENABLED", "true")
    monkeypatch.setenv("SMART_AO_RAG_INDEXING_ENABLED", "on")

    knowledge_embeddings._require_indexing_enabled()

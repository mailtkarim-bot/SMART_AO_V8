from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

DEFAULT_BGE_MODEL_ID = "BAAI/bge-m3"


class BgeEmbeddingProvider:
    """Local BGE adapter; model loading is lazy and never happens on import."""

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_BGE_MODEL_ID,
        cache_dir: Path | None = None,
        local_files_only: bool = True,
        batch_size: int = 8,
        max_seq_length: int = 8192,
    ) -> None:
        if not model_id.strip():
            raise ValueError("model_id must not be empty")
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_seq_length < 1 or max_seq_length > 8192:
            raise ValueError("max_seq_length must be between 1 and 8192")
        self._model_id = model_id
        self._cache_dir = cache_dir
        self._local_files_only = local_files_only
        self._batch_size = batch_size
        self._max_seq_length = max_seq_length
        self._model: Any | None = None

    @property
    def model_id(self) -> str:
        return self._model_id

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise ValueError("embedding text must not be empty")
        model = self._get_model()
        encoded = model.encode(
            list(texts),
            batch_size=self._batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [tuple(float(value) for value in vector) for vector in encoded]

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "BGE local adapter requires the optional 'rag' dependency group"
                ) from exc
            kwargs: dict[str, object] = {
                "device": "cpu",
                "local_files_only": self._local_files_only,
            }
            if self._cache_dir is not None:
                kwargs["cache_folder"] = str(self._cache_dir)
            self._model = SentenceTransformer(self._model_id, **kwargs)
            self._model.max_seq_length = self._max_seq_length
        return self._model

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Final
from uuid import UUID

MAX_RETRIEVAL_TEXT_CHARS: Final = 16_000
MAX_TOP_K: Final = 50


class DataClassification(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL_OPERATIONAL = "INTERNAL_OPERATIONAL"
    PERSONAL_DATA = "PERSONAL_DATA"
    FINANCIAL_PRIVATE = "FINANCIAL_PRIVATE"


@dataclass(frozen=True, slots=True)
class RetrievalScope:
    tenant_id: UUID
    case_id: UUID
    dce_version_id: UUID
    allowed_classifications: frozenset[DataClassification] = field(
        default_factory=lambda: frozenset(
            {
                DataClassification.PUBLIC,
                DataClassification.INTERNAL_OPERATIONAL,
            }
        )
    )

    def __post_init__(self) -> None:
        if not self.allowed_classifications:
            raise ValueError("allowed_classifications must not be empty")


@dataclass(frozen=True, slots=True)
class RetrievalChunk:
    chunk_id: UUID
    tenant_id: UUID
    case_id: UUID
    dce_version_id: UUID
    source_fragment_id: UUID
    ordinal: int
    text: str
    locator: dict[str, object]
    classification: DataClassification

    def __post_init__(self) -> None:
        if self.ordinal < 1:
            raise ValueError("ordinal must be positive")
        if not self.text.strip():
            raise ValueError("text must not be empty")
        if len(self.text) > MAX_RETRIEVAL_TEXT_CHARS:
            raise ValueError("text exceeds retrieval limit")
        if not self.locator:
            raise ValueError("locator must not be empty")

    def is_visible_in(self, scope: RetrievalScope) -> bool:
        return (
            self.tenant_id == scope.tenant_id
            and self.case_id == scope.case_id
            and self.dce_version_id == scope.dce_version_id
            and self.classification in scope.allowed_classifications
        )


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("embedding must not be empty")
        if any(not isfinite(value) for value in self.values):
            raise ValueError("embedding must contain finite values")

    @property
    def dimension(self) -> int:
        return len(self.values)


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    chunk: RetrievalChunk
    score: float
    embedding_model: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be between 0 and 1")
        if not self.embedding_model.strip():
            raise ValueError("embedding_model must not be empty")

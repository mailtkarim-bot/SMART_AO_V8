from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_fragment_id: UUID
    dce_version_id: UUID
    score: float = Field(ge=0.0, le=1.0)
    excerpt: str = Field(min_length=1, max_length=1_000)
    locator: dict[str, object]
    embedding_model: str = Field(min_length=1, max_length=180)


class KnowledgeSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: UUID
    query: str = Field(min_length=1, max_length=500)
    results: list[KnowledgeSearchResult]

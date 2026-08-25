"""Public contracts for authenticated BOAMP search."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicNoticeContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notice_id: str = Field(min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=500)
    publication_date: date | None = None
    response_deadline: datetime | None = None
    department_codes: tuple[str, ...] = Field(default=(), max_length=100)
    market_types: tuple[str, ...] = Field(default=(), max_length=50)
    status: str | None = Field(default=None, max_length=100)


class PublicNoticeSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(ge=1, le=50)
    offset: int = Field(ge=0, le=10_000)
    results: list[PublicNoticeContract]

    # Kept as an explicit technical scope marker, never serialized as tenant data.
    scope: str = Field(default="PUBLIC_TENDER", frozen=True)
    actor_tenant_id: UUID | None = Field(default=None, exclude=True)

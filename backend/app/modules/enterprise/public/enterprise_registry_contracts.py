"""Public contracts for read-only Sirene lookup."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EnterpriseRegistryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    siren: str = Field(min_length=9, max_length=9, pattern=r"^\d{9}$")
    legal_name: str | None = Field(default=None, max_length=500)
    active: bool | None = None
    activity_code: str | None = Field(default=None, max_length=20)
    source: str = Field(default="INSEE_SIRENE", frozen=True)

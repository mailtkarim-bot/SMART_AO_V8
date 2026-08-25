"""Public HTTP contracts for the first Case entrypoint."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    title: str = Field(min_length=1, max_length=240)
    object_description: str = Field(min_length=1, max_length=10_000)
    consultation_id: UUID | None = None
    consultation_revision: int | None = Field(default=None, ge=0)
    scope_kind: Literal["SINGLE_LOT", "MULTI_LOT", "TRANCHE", "VARIANT", "CUSTOM"]
    lot_numbers: tuple[str, ...] = ()
    tranche_reference: str | None = Field(default=None, max_length=240)
    variant_reference: str | None = Field(default=None, max_length=240)
    scope_justification: str | None = Field(default=None, max_length=2_000)
    origin_kind: Literal["MANUAL", "OPPORTUNITY", "IMPORT", "CLIENT_REQUEST"] = "MANUAL"
    origin_rationale: str | None = Field(default=None, max_length=2_000)
    origin_reference_id: UUID | None = None


class CreateCaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["CASE_CREATED"]
    case_id: UUID
    version: int = Field(ge=0)
    event_ids: list[UUID]
    navigation: Literal["CASE_OVERVIEW"] = "CASE_OVERVIEW"
    replayed: bool = False

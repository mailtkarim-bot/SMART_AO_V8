from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConditionalGoConditionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition_id: UUID
    label: str = Field(min_length=1, max_length=500)
    owner_actor_id: UUID
    due_at: datetime | None = None
    due_date_absence_reason: str | None = Field(default=None, max_length=1_000)
    failure_consequence: str = Field(min_length=1, max_length=1_000)


class FinalizeGoNoGoDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    expected_revision: int = Field(ge=0)
    displayed_fingerprint: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$"
    )
    outcome: Literal["GO", "CONDITIONAL_GO", "NO_GO"]
    justification: str = Field(min_length=1, max_length=4_000)
    conditions: tuple[ConditionalGoConditionRequest, ...] = Field(default=(), max_length=32)


class FinalizeGoNoGoDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["DECISION_FINALIZED"]
    decision_id: UUID
    outcome: Literal["GO", "CONDITIONAL_GO", "NO_GO"]
    condition_count: int = Field(ge=0, le=32)
    version: int
    event_ids: list[UUID]
    replayed: bool

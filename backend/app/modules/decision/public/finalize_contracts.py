from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FinalizeGoNoGoDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    expected_revision: int = Field(ge=0)
    displayed_fingerprint: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$"
    )
    outcome: Literal["GO", "NO_GO"]
    justification: str = Field(min_length=1, max_length=4_000)


class FinalizeGoNoGoDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["DECISION_FINALIZED"]
    decision_id: UUID
    outcome: Literal["GO", "NO_GO"]
    version: int
    event_ids: list[UUID]
    replayed: bool

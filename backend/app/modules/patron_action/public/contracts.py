from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreatePatronActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    action_id: UUID
    case_id: UUID | None = None
    functional_key: str = Field(min_length=1, max_length=240)
    action_type: Literal[
        "REVIEW_PREPARATION",
        "CONTROL_SUBMISSION",
        "VALIDATE_PRICE",
        "DECIDE_GO_NO_GO",
    ]
    severity: Literal["URGENT", "BLOCKING", "AT_RISK", "MONITOR"]
    title: str = Field(min_length=1, max_length=240)
    why_now: str = Field(min_length=1, max_length=1000)
    impact: str = Field(min_length=1, max_length=1000)
    recommended_action: str = Field(min_length=1, max_length=1000)
    due_at: datetime | None = None
    source_refs: list[str] = Field(max_length=32)


class TransitionPatronActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    transition_id: UUID
    expected_revision: int = Field(ge=1)
    target_state: Literal["IN_PROGRESS", "WAITING", "COMPLETED", "ABANDONED"]
    reason_code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z0-9_]+$")


class PatronActionCommandResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["PATRON_ACTION_CREATED"]
    aggregate_id: UUID
    aggregate_revision: int = Field(ge=1)
    event_ids: list[UUID]
    replayed: bool = False


class PatronActionTransitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["PATRON_ACTION_TRANSITIONED"]
    aggregate_id: UUID
    aggregate_revision: int = Field(ge=2)
    event_ids: list[UUID]
    replayed: bool = False


class PatronActionProjectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: UUID
    case_id: UUID | None
    functional_key: str
    action_type: str
    severity: Literal["URGENT", "BLOCKING", "AT_RISK", "MONITOR"]
    state: Literal["OPEN", "IN_PROGRESS", "WAITING", "COMPLETED", "ABANDONED"]
    title: str
    why_now: str
    impact: str
    recommended_action: str
    due_at: datetime | None
    source_refs: list[str]
    aggregate_revision: int = Field(ge=1)


class PatronActionQueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PatronActionProjectionResponse]
    open_count: int = Field(ge=0)

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InfoBlockerRequestBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None


class CreateInformationRequestHttpRequest(InfoBlockerRequestBase):
    expected_task_revision: int = Field(ge=0)
    request_kind: Literal[
        "MISSING_SOURCE",
        "CLARIFICATION",
        "OWNER_CONFIRMATION",
        "DEADLINE_CONFIRMATION",
    ]
    subject: str = Field(min_length=1, max_length=240)
    question: str = Field(min_length=1, max_length=4_000)
    requested_object: str = Field(min_length=1, max_length=1_000)
    reason: str = Field(min_length=1, max_length=2_000)
    priority: Literal["LOW", "NORMAL", "HIGH", "CRITICAL"] = "NORMAL"
    due_at: datetime | None = None


class RecordInformationResponseHttpRequest(InfoBlockerRequestBase):
    expected_revision: int = Field(ge=0)
    response_text: str = Field(min_length=1, max_length=8_000)
    source_locator: str | None = Field(default=None, max_length=500)
    outcome: Literal["ANSWERED", "NOT_AVAILABLE", "NEEDS_CLARIFICATION"]


class DeclareTaskBlockerHttpRequest(InfoBlockerRequestBase):
    expected_revision: int = Field(ge=0)
    blocker_kind: Literal[
        "MISSING_INFORMATION",
        "EXTERNAL_DEPENDENCY",
        "SOURCE_CONFLICT",
        "REVIEW_REQUIRED",
    ]
    description: str = Field(min_length=1, max_length=4_000)
    source_locator: str | None = Field(default=None, max_length=500)
    resolution_owner: Literal["COLLABORATEUR", "PATRON_ADMIN", "EXTERNAL_PARTY"]


class ResolveTaskBlockerHttpRequest(InfoBlockerRequestBase):
    expected_revision: int = Field(ge=0)
    resolution_note: str = Field(min_length=1, max_length=4_000)


class InfoBlockerAggregateReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aggregate_type: Literal["InformationRequest", "CollaboratorTask"]
    aggregate_id: UUID
    aggregate_revision: int = Field(ge=0)


class InfoBlockerCommandResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal[
        "INFORMATION_REQUEST_CREATED",
        "INFORMATION_REQUEST_ANSWERED",
        "TASK_BLOCKED",
        "TASK_UNBLOCKED",
    ]
    aggregate_refs: list[InfoBlockerAggregateReference]
    event_ids: list[UUID]
    replayed: bool = False


class InformationResponseProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_id: UUID
    request_revision: int = Field(ge=0)
    outcome: Literal["ANSWERED", "NOT_AVAILABLE", "NEEDS_CLARIFICATION"]
    response_text: str
    source_locator: str | None
    created_at: datetime


class InformationRequestProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    task_id: UUID
    request_kind: str
    subject: str
    question: str
    requested_object: str
    reason: str
    priority: Literal["LOW", "NORMAL", "HIGH", "CRITICAL"]
    state: Literal["OPEN", "ANSWERED", "CLOSED", "CANCELLED"]
    due_at: datetime | None
    aggregate_revision: int = Field(ge=0)
    responses: list[InformationResponseProjection]


class TaskBlockerProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocker_id: UUID
    task_id: UUID
    task_revision: int = Field(ge=0)
    blocker_kind: str
    description: str
    source_locator: str | None
    resolution_owner: str
    state: Literal["OPEN", "RESOLVED"]
    resolution_note: str | None
    resolved_at: datetime | None


class CollaboratorTaskWorkflowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    state: Literal["READY", "IN_PROGRESS", "BLOCKED", "COMPLETED", "ABANDONED"]
    aggregate_revision: int = Field(ge=0)
    information_requests: list[InformationRequestProjection]
    blockers: list[TaskBlockerProjection]

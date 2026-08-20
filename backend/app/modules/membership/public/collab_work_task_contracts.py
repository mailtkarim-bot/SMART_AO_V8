from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CollaboratorTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None


class CreateCollaboratorTaskRequest(CollaboratorTaskRequest):
    requirement_id: UUID
    task_kind: Literal[
        "REQUIREMENT_CHECK",
        "DOCUMENT_PREPARATION",
        "SITE_VISIT",
        "TECHNICAL_PREPARATION",
        "ADMINISTRATIVE_PREPARATION",
    ]
    title: str = Field(min_length=1, max_length=240)
    objective: str = Field(min_length=1, max_length=2_000)
    due_at: datetime | None = None


class ClaimCollaboratorTaskRequest(CollaboratorTaskRequest):
    expected_revision: int = Field(ge=0)


class RecordCollaboratorTaskResultRequest(CollaboratorTaskRequest):
    expected_revision: int = Field(ge=0)
    result_text: str = Field(min_length=1, max_length=8_000)
    source_locator: str | None = Field(default=None, max_length=500)
    outcome: Literal["RECORDED", "NOT_APPLICABLE", "UNABLE_TO_COMPLETE"]


class CompleteCollaboratorTaskRequest(CollaboratorTaskRequest):
    expected_revision: int = Field(ge=0)


class CollaboratorTaskAggregateReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aggregate_type: Literal["CollaboratorTask"]
    aggregate_id: UUID
    aggregate_revision: int = Field(ge=0)


class CollaboratorTaskProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    case_id: UUID
    assignment_id: UUID
    requirement_id: UUID
    task_kind: str
    title: str
    objective: str
    priority: Literal["LOW", "NORMAL", "HIGH", "CRITICAL"]
    state: Literal["READY", "IN_PROGRESS", "BLOCKED", "COMPLETED", "ABANDONED"]
    due_at: datetime | None
    aggregate_revision: int = Field(ge=0)


class CollaboratorTaskListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: UUID
    tasks: list[CollaboratorTaskProjection]


class CollaboratorTaskCommandResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal[
        "TASK_CREATED",
        "TASK_CLAIMED",
        "TASK_UPDATED",
        "TASK_COMPLETED",
    ]
    aggregate_refs: list[CollaboratorTaskAggregateReference]
    event_ids: list[UUID]
    replayed: bool = False

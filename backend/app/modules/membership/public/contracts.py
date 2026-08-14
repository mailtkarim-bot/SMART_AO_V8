"""Closed HTTP projections for collaborator Assignment history reads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssignmentHistoryItemResponse(PublicResponseModel):
    record_id: UUID
    kind: Literal["ACKNOWLEDGEMENT", "CLARIFICATION_REQUEST", "UNAVAILABILITY_REPORT"]
    recorded_at: datetime
    assignment_revision: int | None = Field(default=None, ge=0)
    operational_state: Literal["RECORDED", "OPEN"]
    clarification_kind: Literal[
        "SCOPE",
        "PRIORITY",
        "DEADLINE",
        "DOCUMENT",
        "RESPONSIBILITY",
        "OTHER",
    ] | None = None
    priority: Literal["LOW", "NORMAL", "HIGH"] | None = None
    reason_kind: Literal[
        "SICKNESS",
        "LEAVE",
        "CAPACITY_CONFLICT",
        "SKILL_GAP",
        "ACCESS_PROBLEM",
        "OTHER",
    ] | None = None
    unavailable_from: datetime | None = None
    unavailable_until: datetime | None = None
    known_deadline_impact: bool | None = None


class AssignmentHistoryResponse(PublicResponseModel):
    assignment_id: UUID
    case_id: UUID
    case_lifecycle: str
    items: list[AssignmentHistoryItemResponse]

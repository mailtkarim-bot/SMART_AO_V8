from __future__ import annotations

from uuid import UUID

from app.modules.opportunity.application.boamp_qualification import (
    QualificationDecision,
    QualificationReason,
)
from pydantic import BaseModel, ConfigDict, Field


class BoampObservationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: UUID
    source_notice_id: str
    title: str | None
    publication_date: str | None
    response_deadline: str | None
    department_codes: list[str]
    market_types: list[str]
    source_status: str | None
    score_version: str
    score: int = Field(ge=0, le=100)
    score_explanation: dict[str, object]
    fingerprint_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class BoampObservationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[BoampObservationResponse]


class BoampObservationQualificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: QualificationDecision
    reason_code: QualificationReason
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None


class BoampQualificationReceiptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    qualification_id: UUID
    event_id: UUID
    replayed: bool


class BoampObservationCreateCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None


class BoampCaseCreationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: str = "CASE_CREATED"
    case_id: UUID
    version: int = Field(ge=0)
    event_ids: list[UUID]
    replayed: bool

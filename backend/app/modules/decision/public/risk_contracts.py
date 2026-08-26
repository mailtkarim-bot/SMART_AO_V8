from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TransitionStructuredRiskTreatmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    risk_id: UUID
    expected_revision: int = Field(ge=1)
    to_treatment: Literal["ACCEPTED", "MITIGATED"]
    evidence_excerpt: str = Field(min_length=1, max_length=2_000)
    evidence_locator: dict[str, object]
    evidence_start_byte_offset: int = Field(ge=0)
    evidence_end_byte_offset: int = Field(gt=0)
    rationale: str = Field(min_length=1, max_length=2_000)


class StructuredRiskProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_id: UUID
    case_id: UUID
    dce_version_id: UUID
    risk_code: str
    category: Literal["CCAP", "CCTP"]
    title: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    likelihood: Literal["RARE", "POSSIBLE", "LIKELY", "ALMOST_CERTAIN"]
    treatment: Literal["OPEN", "ACCEPTED", "MITIGATED"]
    revision: int = Field(ge=1)
    due_at: datetime | None
    latest_treatment_evidence: dict[str, object] | None


class RegisterStructuredRiskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    risk_id: UUID
    dce_version_id: UUID
    source_fragment_id: UUID
    category: Literal["CCAP", "CCTP"]
    risk_code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=240)
    statement: str = Field(min_length=1, max_length=4_000)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    likelihood: Literal["RARE", "POSSIBLE", "LIKELY", "ALMOST_CERTAIN"]
    source_excerpt: str = Field(min_length=1, max_length=2_000)
    source_locator: dict[str, object]
    start_byte_offset: int = Field(ge=0)
    end_byte_offset: int = Field(gt=0)
    due_at: datetime | None = None


class TransitionStructuredRiskTreatmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["DECISION_RISK_TREATMENT_TRANSITIONED"]
    risk_id: UUID
    version: int
    treatment: Literal["ACCEPTED", "MITIGATED"]
    event_ids: list[UUID]
    replayed: bool


class StructuredRiskCommandResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["DECISION_RISK_REGISTERED"]
    risk_id: UUID
    version: int
    event_ids: list[UUID]
    replayed: bool

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LinkRiskToRequirementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    link_id: UUID
    requirement_id: UUID
    dce_version_id: UUID
    relationship: Literal["IMPACTS", "MITIGATES", "CONSTRAINS"]
    rationale: str = Field(min_length=1, max_length=4_000)


class RiskRequirementLinkCommandResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["DECISION_RISK_REQUIREMENT_LINKED"]
    link_id: UUID
    version: int
    event_ids: list[UUID]
    replayed: bool

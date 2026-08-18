from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreatePricingScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    scenario_id: UUID
    source_snapshot_id: UUID
    scenario_key: str = Field(min_length=1, max_length=120)
    scenario_type: Literal["BASE", "PRUDENT", "CUSTOM"]
    sales_adjustment_bps: int = Field(ge=-5000, le=10000)
    cost_adjustment_bps: int = Field(ge=-5000, le=10000)
    assumptions: dict[str, object]


class PricingScenarioResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: UUID
    case_id: UUID
    scenario_key: str
    scenario_type: str
    version: int = Field(ge=1)
    state: Literal["DRAFT", "SELECTED", "ARCHIVED"]
    assumptions: dict[str, object]
    sales_total_minor: int
    total_cost_minor: int
    gross_margin_minor: int
    gross_margin_rate_bps: int
    source_snapshot_revision: int


class PricingScenarioCommandResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["PRICING_SCENARIO_CREATED"]
    scenario_id: UUID
    version: int
    event_ids: list[UUID]
    replayed: bool = False

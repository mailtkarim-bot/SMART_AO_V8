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
    penalty_reserve_minor: int = Field(default=0, ge=0)
    retention_reserve_minor: int = Field(default=0, ge=0)
    guarantee_reserve_minor: int = Field(default=0, ge=0)
    floor_margin_rate_bps: int = Field(default=0, ge=0, lt=10000)
    target_margin_rate_bps: int = Field(default=0, ge=0, lt=10000)
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
    penalty_reserve_minor: int
    retention_reserve_minor: int
    guarantee_reserve_minor: int
    floor_margin_rate_bps: int
    target_margin_rate_bps: int
    break_even_sales_minor: int
    floor_sales_minor: int
    target_sales_minor: int
    source_snapshot_revision: int


class TransitionPricingScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    transition_id: UUID
    expected_version: int = Field(ge=1)
    target_state: Literal["SELECTED", "ARCHIVED"]
    reason_code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z0-9_]+$")


class PricingScenarioStateChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    transition_id: UUID
    expected_version: int = Field(ge=1)
    reason_code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z0-9_]+$")


class PricingScenarioTransitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["PRICING_SCENARIO_TRANSITIONED"]
    scenario_id: UUID
    version: int = Field(ge=2)
    event_ids: list[UUID]
    replayed: bool = False


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

from typing import Literal
from uuid import UUID

from pydantic import Field

from app.platform.events.command_contracts import ApplicationCommand


class CreatePricingScenarioCommand(ApplicationCommand):
    """Create one private scenario from a published official snapshot."""

    command_type = "CreatePricingScenario"

    scenario_id: UUID
    case_id: UUID
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

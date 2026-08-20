from typing import Literal
from uuid import UUID

from pydantic import Field

from app.platform.events.command_contracts import ApplicationCommand


class TransitionPricingScenarioCommand(ApplicationCommand):
    """Select or archive one private pricing scenario as a patron."""

    command_type = "TransitionPricingScenario"

    transition_id: UUID
    scenario_id: UUID
    expected_version: int = Field(ge=1)
    target_state: Literal["SELECTED", "ARCHIVED"]
    reason_code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z0-9_]+$")


class SelectPricingScenarioCommand(TransitionPricingScenarioCommand):
    command_type = "SelectPricingScenario"
    target_state: Literal["SELECTED"] = "SELECTED"


class ArchivePricingScenarioCommand(TransitionPricingScenarioCommand):
    command_type = "ArchivePricingScenario"
    target_state: Literal["ARCHIVED"] = "ARCHIVED"

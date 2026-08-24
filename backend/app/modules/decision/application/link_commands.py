from typing import Literal
from uuid import UUID

from pydantic import Field

from app.platform.events.command_contracts import ApplicationCommand


class LinkRiskToRequirementCommand(ApplicationCommand):
    """Link one registered risk to one human-confirmed DCE requirement."""

    command_type = "LinkRiskToRequirement"

    link_id: UUID
    case_id: UUID
    risk_id: UUID
    requirement_id: UUID
    dce_version_id: UUID
    relationship: Literal["IMPACTS", "MITIGATES", "CONSTRAINS"]
    rationale: str = Field(min_length=1, max_length=4_000)

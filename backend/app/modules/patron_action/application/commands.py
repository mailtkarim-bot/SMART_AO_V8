from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.platform.events.command_contracts import ApplicationCommand


class CreatePatronActionCommand(ApplicationCommand):
    """Create one explainable action in the patron decision queue."""

    command_type = "CreatePatronAction"

    action_id: UUID
    case_id: UUID | None = None
    functional_key: str = Field(min_length=1, max_length=240)
    action_type: Literal[
        "REVIEW_PREPARATION",
        "CONTROL_SUBMISSION",
        "VALIDATE_PRICE",
        "DECIDE_GO_NO_GO",
    ]
    severity: Literal["URGENT", "BLOCKING", "AT_RISK", "MONITOR"]
    title: str = Field(min_length=1, max_length=240)
    why_now: str = Field(min_length=1, max_length=1000)
    impact: str = Field(min_length=1, max_length=1000)
    recommended_action: str = Field(min_length=1, max_length=1000)
    due_at: datetime | None = None
    source_refs: list[str] = Field(max_length=32)

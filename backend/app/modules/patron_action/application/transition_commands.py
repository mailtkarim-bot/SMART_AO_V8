from typing import Literal
from uuid import UUID

from pydantic import Field

from app.platform.events.command_contracts import ApplicationCommand


class TransitionPatronActionCommand(ApplicationCommand):
    """Move an action through a closed, patron-controlled workflow."""

    command_type = "TransitionPatronAction"

    transition_id: UUID
    action_id: UUID
    expected_revision: int = Field(ge=1)
    target_state: Literal["IN_PROGRESS", "WAITING", "COMPLETED", "ABANDONED"]
    reason_code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z0-9_]+$")

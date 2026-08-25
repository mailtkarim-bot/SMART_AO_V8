from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.platform.events.command_contracts import ApplicationCommand


class ConditionalGoConditionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition_id: UUID
    label: str = Field(min_length=1, max_length=500)
    owner_actor_id: UUID
    due_at: datetime | None = None
    due_date_absence_reason: str | None = Field(default=None, max_length=1_000)
    failure_consequence: str = Field(min_length=1, max_length=1_000)


class FinalizeGoNoGoDecisionCommand(ApplicationCommand):
    """Finalize a patron GO or NO-GO against one displayed context fingerprint."""

    command_type = "FinalizeGoNoGoDecision"

    decision_id: UUID
    case_id: UUID
    expected_revision: int = Field(ge=0)
    displayed_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    outcome: Literal["GO", "CONDITIONAL_GO", "NO_GO"]
    justification: str = Field(min_length=1, max_length=4_000)
    conditions: tuple[ConditionalGoConditionInput, ...] = Field(default=(), max_length=32)

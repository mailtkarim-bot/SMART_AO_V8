from typing import Literal
from uuid import UUID

from pydantic import Field

from app.platform.events.command_contracts import ApplicationCommand


class FinalizeGoNoGoDecisionCommand(ApplicationCommand):
    """Finalize a patron GO or NO-GO against one displayed context fingerprint."""

    command_type = "FinalizeGoNoGoDecision"

    decision_id: UUID
    case_id: UUID
    expected_revision: int = Field(ge=0)
    displayed_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    outcome: Literal["GO", "NO_GO"]
    justification: str = Field(min_length=1, max_length=4_000)

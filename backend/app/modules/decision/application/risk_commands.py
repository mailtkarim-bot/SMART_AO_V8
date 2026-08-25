from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.platform.events.command_contracts import ApplicationCommand


class RegisterStructuredRiskCommand(ApplicationCommand):
    """Register one immutable patron risk sourced from a DCE extraction fragment."""

    command_type = "RegisterStructuredRisk"

    risk_id: UUID
    case_id: UUID
    dce_version_id: UUID
    source_fragment_id: UUID
    category: Literal["CCAP", "CCTP"]
    risk_code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=240)
    statement: str = Field(min_length=1, max_length=4_000)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    likelihood: Literal["RARE", "POSSIBLE", "LIKELY", "ALMOST_CERTAIN"]
    source_excerpt: str = Field(min_length=1, max_length=2_000)
    source_locator: dict[str, object]
    start_byte_offset: int = Field(ge=0)
    end_byte_offset: int = Field(gt=0)
    due_at: datetime | None = None

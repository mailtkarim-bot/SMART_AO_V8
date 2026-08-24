"""Application commands for the Case bounded context."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from app.platform.events.command_contracts import ApplicationCommand


class CreateCaseCommand(ApplicationCommand):
    """Create one affair from a manual or referenced business origin."""

    command_type = "CreateCase"

    case_id: UUID
    title: str = Field(min_length=1, max_length=240)
    object_description: str = Field(min_length=1, max_length=10_000)
    consultation_id: UUID | None = None
    consultation_revision: int | None = Field(default=None, ge=0)
    scope_kind: Literal["SINGLE_LOT", "MULTI_LOT", "TRANCHE", "VARIANT", "CUSTOM"]
    lot_numbers: tuple[str, ...] = ()
    tranche_reference: str | None = Field(default=None, max_length=240)
    variant_reference: str | None = Field(default=None, max_length=240)
    scope_justification: str | None = Field(default=None, max_length=2_000)
    origin_kind: Literal["MANUAL", "OPPORTUNITY", "IMPORT", "CLIENT_REQUEST"] = "MANUAL"
    origin_rationale: str | None = Field(default=None, max_length=2_000)
    origin_reference_id: UUID | None = None

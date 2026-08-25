from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.platform.events.command_contracts import ApplicationCommand


class DecisionContextReferenceInput(BaseModel):
    """One immutable aggregate reference included in a frozen Decision context."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    aggregate_type: Literal[
        "CASE",
        "DCE_VERSION",
        "DCE_REQUIREMENT",
        "DECISION_RISK",
        "PRICING_SCENARIO",
    ]
    aggregate_id: UUID
    aggregate_revision: int = Field(ge=0)
    content_hash: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[a-fA-F0-9]{64}$",
    )
    reference_role: str = Field(min_length=1, max_length=80)


class CreateDecisionCommand(ApplicationCommand):
    """Create one patron-owned GO/NO-GO Decision draft for an active Case."""

    command_type = "CreateDecision"

    decision_id: UUID
    case_id: UUID
    decision_type: Literal["GO_NO_GO"] = "GO_NO_GO"
    scope_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[a-fA-F0-9]{64}$",
    )


class FreezeDecisionContextCommand(ApplicationCommand):
    """Freeze the exact facts displayed to the patron before finalization."""

    command_type = "FreezeDecisionContext"

    decision_id: UUID
    case_id: UUID
    context_id: UUID
    expected_revision: int = Field(ge=0)
    rationale: str = Field(min_length=1, max_length=4_000)
    unknowns: tuple[str, ...] = Field(default=(), max_length=100)
    risks: tuple[str, ...] = Field(default=(), max_length=100)
    references: tuple[DecisionContextReferenceInput, ...] = Field(min_length=1, max_length=500)


class ResolveDecisionConditionCommand(ApplicationCommand):
    """Resolve one open CONDITIONAL_GO condition with bounded evidence or reason."""

    command_type = "ResolveDecisionCondition"

    decision_id: UUID
    case_id: UUID
    condition_id: UUID
    transition_id: UUID
    expected_revision: int = Field(ge=0)
    target_status: Literal["SATISFIED", "FAILED"]
    evidence_reference: str | None = Field(default=None, max_length=2_000)
    failure_reason: str | None = Field(default=None, max_length=2_000)

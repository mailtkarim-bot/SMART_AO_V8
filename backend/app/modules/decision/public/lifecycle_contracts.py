from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DecisionContextReferenceRequest(BaseModel):
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


class CreateDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    scope_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[a-fA-F0-9]{64}$",
    )


class CreateDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["DECISION_DRAFT_CREATED"]
    decision_id: UUID
    version: int = Field(ge=0)
    event_ids: list[UUID]
    replayed: bool


class FreezeDecisionContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    context_id: UUID
    expected_revision: int = Field(ge=0)
    rationale: str = Field(min_length=1, max_length=4_000)
    unknowns: tuple[str, ...] = Field(default=(), max_length=100)
    risks: tuple[str, ...] = Field(default=(), max_length=100)
    references: tuple[DecisionContextReferenceRequest, ...] = Field(min_length=1, max_length=500)


class FreezeDecisionContextResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["DECISION_CONTEXT_FROZEN"]
    decision_id: UUID
    context_id: UUID
    fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-fA-F0-9]{64}$")
    version: int = Field(ge=1)
    event_ids: list[UUID]
    replayed: bool


class ResolveDecisionConditionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    transition_id: UUID
    expected_revision: int = Field(ge=0)
    target_status: Literal["SATISFIED", "FAILED"]
    evidence_reference: str | None = Field(default=None, max_length=2_000)
    failure_reason: str | None = Field(default=None, max_length=2_000)


class ResolveDecisionConditionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["DECISION_CONDITION_RESOLVED"]
    decision_id: UUID
    condition_id: UUID
    status: Literal["SATISFIED", "FAILED"]
    version: int = Field(ge=1)
    event_ids: list[UUID]
    replayed: bool

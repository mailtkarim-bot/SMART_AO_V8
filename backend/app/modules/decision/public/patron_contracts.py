from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DecisionConditionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition_id: UUID
    label: str
    status: Literal["OPEN", "SATISFIED", "FAILED", "WAIVED"]
    due_at: datetime | None
    failure_consequence: str


class DecisionSourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aggregate_type: str
    aggregate_id: UUID
    aggregate_revision: int
    role: str


class PatronDecisionDossierResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: UUID
    case_id: UUID
    decision_type: str
    lifecycle: str
    outcome: str
    validity: str
    context_status: str
    final_justification: str | None
    known: list[object]
    unknowns: list[object]
    risks: list[object]
    conditions: list[DecisionConditionResponse]
    sources: list[DecisionSourceResponse]

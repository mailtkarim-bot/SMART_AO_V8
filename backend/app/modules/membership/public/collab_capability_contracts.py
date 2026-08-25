from __future__ import annotations

from typing import TYPE_CHECKING, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from app.modules.membership.application.collab_capability_commands import (
        ProposeCapabilityForCaseCommand,
        ReportCapabilityGapCommand,
    )


class CollaboratorCapabilityPublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProposeCapabilityForCaseRequest(CollaboratorCapabilityPublicModel):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    assignment_id: UUID
    capability_id: UUID
    capability_version_id: UUID
    requirement_id: UUID | None = None
    task_id: UUID | None = None
    justification: str = Field(min_length=1, max_length=2_000)
    source_locator: str | None = Field(default=None, max_length=500)

    def to_command(self, *, case_id: UUID) -> ProposeCapabilityForCaseCommand:
        from app.modules.membership.application.collab_capability_commands import (
            ProposeCapabilityForCaseCommand,
        )

        return ProposeCapabilityForCaseCommand(
            **self.model_dump(),
            case_id=case_id,
            proposal_id=uuid5(NAMESPACE_URL, f"case-capability-proposal:{self.command_id}"),
        )


class ReportCapabilityGapRequest(CollaboratorCapabilityPublicModel):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    assignment_id: UUID
    capability_id: UUID | None = None
    requirement_id: UUID | None = None
    task_id: UUID | None = None
    gap_kind: Literal["MISSING", "EXPIRED", "UNAUTHORIZED", "INSUFFICIENT"]
    severity: Literal["INFORMATIONAL", "IMPORTANT", "BLOCKING"]
    reason: str = Field(min_length=1, max_length=2_000)
    source_locator: str | None = Field(default=None, max_length=500)
    recommended_action: str = Field(min_length=1, max_length=1_000)

    def to_command(self, *, case_id: UUID) -> ReportCapabilityGapCommand:
        from app.modules.membership.application.collab_capability_commands import (
            ReportCapabilityGapCommand,
        )

        return ReportCapabilityGapCommand(
            **self.model_dump(),
            case_id=case_id,
            gap_id=uuid5(NAMESPACE_URL, f"case-capability-gap:{self.command_id}"),
        )


class CollaboratorCapabilityReceiptResponse(CollaboratorCapabilityPublicModel):
    status: Literal["SUCCEEDED"]
    command_id: UUID
    idempotency_key: UUID
    result_code: str
    aggregate_refs: list[dict[str, object]]
    event_ids: list[UUID]
    replayed: bool


class CapabilityProposalResponse(CollaboratorCapabilityPublicModel):
    proposal_id: UUID
    case_id: UUID
    assignment_id: UUID
    capability_id: UUID
    capability_version_id: UUID
    requirement_id: UUID | None
    task_id: UUID | None
    state: Literal["PROPOSED", "TO_REVIEW"]
    validity_state: Literal["CURRENT", "EXPIRED", "UNKNOWN"]
    justification: str
    source_locator: str | None


class CapabilityGapResponse(CollaboratorCapabilityPublicModel):
    gap_id: UUID
    case_id: UUID
    assignment_id: UUID
    capability_id: UUID | None
    requirement_id: UUID | None
    task_id: UUID | None
    gap_kind: Literal["MISSING", "EXPIRED", "UNAUTHORIZED", "INSUFFICIENT"]
    severity: Literal["INFORMATIONAL", "IMPORTANT", "BLOCKING"]
    reason: str
    source_locator: str | None
    recommended_action: str


class CollaboratorCapabilityAssessmentResponse(CollaboratorCapabilityPublicModel):
    proposals: list[CapabilityProposalResponse]
    gaps: list[CapabilityGapResponse]

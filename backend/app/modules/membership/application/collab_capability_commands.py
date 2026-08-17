from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.modules.dce.application.commands import ApplicationCommand
from app.modules.membership.application.collab_work_task_commands import _contains_forbidden


class ProposeCapabilityForCaseCommand(ApplicationCommand):
    """Propose one enterprise capability version for a bounded Case scope."""

    command_type = "ProposeCapabilityForCase"

    proposal_id: UUID
    case_id: UUID
    assignment_id: UUID
    capability_id: UUID
    capability_version_id: UUID
    requirement_id: UUID | None = None
    task_id: UUID | None = None
    justification: str = Field(min_length=1, max_length=2_000)
    source_locator: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_source_and_text(self) -> ProposeCapabilityForCaseCommand:
        if self.requirement_id is None and self.task_id is None:
            raise ValueError("CAPABILITY_SOURCE_REQUIRED")
        if _contains_forbidden(self.justification, self.source_locator or ""):
            raise ValueError("FINANCIAL_DATA_FORBIDDEN")
        return self


class ReportCapabilityGapCommand(ApplicationCommand):
    """Record one missing, expired, unauthorized or insufficient capability finding."""

    command_type = "ReportCapabilityGap"

    gap_id: UUID
    case_id: UUID
    assignment_id: UUID
    capability_id: UUID | None = None
    requirement_id: UUID | None = None
    task_id: UUID | None = None
    gap_kind: Literal["MISSING", "EXPIRED", "UNAUTHORIZED", "INSUFFICIENT"]
    severity: Literal["INFORMATIONAL", "IMPORTANT", "BLOCKING"]
    reason: str = Field(min_length=1, max_length=2_000)
    source_locator: str | None = Field(default=None, max_length=500)
    recommended_action: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def validate_source_and_text(self) -> ReportCapabilityGapCommand:
        if self.requirement_id is None and self.task_id is None:
            raise ValueError("CAPABILITY_SOURCE_REQUIRED")
        if _contains_forbidden(self.reason, self.source_locator or "", self.recommended_action):
            raise ValueError("FINANCIAL_DATA_FORBIDDEN")
        return self

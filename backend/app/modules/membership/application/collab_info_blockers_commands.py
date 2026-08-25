from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.modules.membership.public.text_safety import contains_forbidden_text
from app.platform.events.command_contracts import ApplicationCommand


class CreateInformationRequestCommand(ApplicationCommand):
    """Create one bounded information request attached to a visible task."""

    command_type = "CreateInformationRequest"

    request_id: UUID
    task_id: UUID
    expected_task_revision: int = Field(ge=0)
    request_kind: Literal[
        "MISSING_SOURCE",
        "CLARIFICATION",
        "OWNER_CONFIRMATION",
        "DEADLINE_CONFIRMATION",
    ]
    subject: str = Field(min_length=1, max_length=240)
    question: str = Field(min_length=1, max_length=4_000)
    requested_object: str = Field(min_length=1, max_length=1_000)
    reason: str = Field(min_length=1, max_length=2_000)
    priority: Literal["LOW", "NORMAL", "HIGH", "CRITICAL"] = "NORMAL"
    due_at: datetime | None = None

    @model_validator(mode="after")
    def reject_financial_content(self) -> CreateInformationRequestCommand:
        if contains_forbidden_text(self.subject, self.question, self.requested_object, self.reason):
            raise ValueError("FINANCIAL_DATA_FORBIDDEN")
        return self


class RecordInformationRequestResponseCommand(ApplicationCommand):
    """Append one versioned operational response to an open request."""

    command_type = "RecordInformationRequestResponse"

    request_id: UUID
    expected_revision: int = Field(ge=0)
    response_text: str = Field(min_length=1, max_length=8_000)
    source_locator: str | None = Field(default=None, max_length=500)
    outcome: Literal["ANSWERED", "NOT_AVAILABLE", "NEEDS_CLARIFICATION"]

    @model_validator(mode="after")
    def reject_financial_content(self) -> RecordInformationRequestResponseCommand:
        if contains_forbidden_text(self.response_text, self.source_locator or ""):
            raise ValueError("FINANCIAL_DATA_FORBIDDEN")
        return self


class DeclareTaskBlockerCommand(ApplicationCommand):
    """Move a task to BLOCKED and append one operational blocker."""

    command_type = "DeclareTaskBlocker"

    task_id: UUID
    expected_revision: int = Field(ge=0)
    blocker_id: UUID
    blocker_kind: Literal[
        "MISSING_INFORMATION",
        "EXTERNAL_DEPENDENCY",
        "SOURCE_CONFLICT",
        "REVIEW_REQUIRED",
    ]
    description: str = Field(min_length=1, max_length=4_000)
    source_locator: str | None = Field(default=None, max_length=500)
    resolution_owner: Literal["COLLABORATEUR", "PATRON_ADMIN", "EXTERNAL_PARTY"]

    @model_validator(mode="after")
    def reject_financial_content(self) -> DeclareTaskBlockerCommand:
        if contains_forbidden_text(self.description, self.source_locator or ""):
            raise ValueError("FINANCIAL_DATA_FORBIDDEN")
        return self


class ResolveTaskBlockerCommand(ApplicationCommand):
    """Resolve one blocker and return the task to an active state."""

    command_type = "ResolveTaskBlocker"

    task_id: UUID
    blocker_id: UUID
    expected_revision: int = Field(ge=0)
    resolution_note: str = Field(min_length=1, max_length=4_000)

    @model_validator(mode="after")
    def reject_financial_content(self) -> ResolveTaskBlockerCommand:
        if contains_forbidden_text(self.resolution_note):
            raise ValueError("FINANCIAL_DATA_FORBIDDEN")
        return self

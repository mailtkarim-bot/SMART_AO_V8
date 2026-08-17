from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.modules.dce.application.commands import ApplicationCommand

_FORBIDDEN_FINANCIAL_TERMS = re.compile(
    r"\b(price|prix|cost|coût|cout|margin|marge|treasury|trésorerie|tresorerie|"
    r"financial|financier|finance|go/no-go|go_no_go|deposit|dépôt|depot|"
    r"submission|soumission|chiffrage)\b",
    re.IGNORECASE,
)


class CreateTaskFromRequirementCommand(ApplicationCommand):
    """Create one bounded operational task from a visible DCE requirement."""

    command_type = "CreateTaskFromRequirement"

    task_id: UUID
    assignment_id: UUID
    case_id: UUID
    requirement_id: UUID
    task_kind: Literal[
        "REQUIREMENT_CHECK",
        "DOCUMENT_PREPARATION",
        "SITE_VISIT",
        "TECHNICAL_PREPARATION",
        "ADMINISTRATIVE_PREPARATION",
    ]
    title: str = Field(min_length=1, max_length=240)
    objective: str = Field(min_length=1, max_length=2_000)
    due_at: datetime | None = None

    @model_validator(mode="after")
    def reject_financial_content(self) -> CreateTaskFromRequirementCommand:
        if _contains_forbidden(self.title, self.objective):
            raise ValueError("FINANCIAL_DATA_FORBIDDEN")
        return self


class ClaimTaskCommand(ApplicationCommand):
    """Move a task from READY to IN_PROGRESS under optimistic concurrency."""

    command_type = "ClaimTask"

    task_id: UUID
    expected_revision: int = Field(ge=0)


class RecordTaskResultCommand(ApplicationCommand):
    """Append a bounded operational result; it is not an Evidence confirmation."""

    command_type = "RecordTaskResult"

    task_id: UUID
    expected_revision: int = Field(ge=0)
    result_text: str = Field(min_length=1, max_length=8_000)
    source_locator: str | None = Field(default=None, max_length=500)
    outcome: Literal["RECORDED", "NOT_APPLICABLE", "UNABLE_TO_COMPLETE"]

    @model_validator(mode="after")
    def validate_result(self) -> RecordTaskResultCommand:
        if _contains_forbidden(self.result_text, self.source_locator or ""):
            raise ValueError("FINANCIAL_DATA_FORBIDDEN")
        return self


class CompleteTaskCommand(ApplicationCommand):
    """Close a task only after an admissible result exists."""

    command_type = "CompleteTask"

    task_id: UUID
    expected_revision: int = Field(ge=0)


def _contains_forbidden(*values: str) -> bool:
    return any(_FORBIDDEN_FINANCIAL_TERMS.search(value) for value in values)

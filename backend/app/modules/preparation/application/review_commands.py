from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.platform.events.command_contracts import ApplicationCommand

_FINANCIAL_TERMS = (
    "prix",
    "coût",
    "cout",
    "marge",
    "trésorerie",
    "tresorerie",
    "chiffrage",
    "devis",
)


def _reject_financial_text(value: str | None) -> str | None:
    if value is not None and any(term in value.casefold() for term in _FINANCIAL_TERMS):
        raise ValueError("FINANCIAL_DATA_FORBIDDEN")
    return value


class RequestPreparationReviewCommand(ApplicationCommand):
    """Request a human review of one immutable technical document version."""

    command_type = "RequestPreparationReview"

    review_id: UUID
    package_id: UUID
    target_document_id: UUID
    target_version: int = Field(gt=0)
    expected_package_revision: int = Field(ge=0)


class DecidePreparationReviewCommand(ApplicationCommand):
    """Record one immutable human review decision."""

    command_type = "DecidePreparationReview"

    review_id: UUID
    package_id: UUID
    target_document_id: UUID
    expected_review_revision: int = Field(ge=1)
    decision_code: Literal["ACCEPTED", "CORRECTIONS_REQUIRED", "REJECTED"]
    decision_note: str | None = Field(default=None, max_length=2000)

    _decision_note_without_finance = field_validator("decision_note", mode="before")(
        _reject_financial_text
    )


class AddPreparationCorrectionCommand(ApplicationCommand):
    """Record one targeted correction without mutating the reviewed target."""

    command_type = "AddPreparationCorrection"

    review_id: UUID
    package_id: UUID
    target_document_id: UUID
    correction_code: Literal[
        "SOURCE_MISSING", "SOURCE_WRONG", "SECTION_INCOMPLETE", "WORDING_UNCLEAR"
    ]
    instruction: str = Field(min_length=1, max_length=2000)
    source_locator: str | None = Field(default=None, max_length=500)

    _instruction_without_finance = field_validator("instruction", mode="before")(
        _reject_financial_text
    )


class CreateTechnicalResponseDraftCommand(ApplicationCommand):
    """Create an immutable, non-financial response draft version."""

    command_type = "CreateTechnicalResponseDraft"

    draft_id: UUID
    package_id: UUID
    source_document_id: UUID
    expected_package_revision: int = Field(ge=0)
    section_codes: list[str] = Field(min_length=1, max_length=32)
    source_refs: list[UUID] = Field(min_length=1, max_length=64)
    responsible_role: Literal["COLLABORATEUR"] = "COLLABORATEUR"

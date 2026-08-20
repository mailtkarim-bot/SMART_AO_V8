from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from app.platform.events.command_contracts import ApplicationCommand


class EvaluatePreparationReadinessCommand(ApplicationCommand):
    """Evaluate the current operational completeness of one preparation package."""

    command_type = "EvaluatePreparationReadiness"

    package_id: UUID
    case_id: UUID
    assignment_id: UUID
    dce_version_id: UUID
    expected_revision: int = Field(ge=0)


class GenerateTechnicalDocumentCommand(ApplicationCommand):
    """Generate one immutable technical document from an admissible readiness."""

    command_type = "GenerateTechnicalDocument"

    package_id: UUID
    document_id: UUID
    expected_revision: int = Field(ge=0)
    readiness_revision: int = Field(ge=1)
    document_kind: Literal["TECHNICAL_RESPONSE"]

from typing import Literal
from uuid import UUID

from pydantic import Field

from app.platform.events.command_contracts import ApplicationCommand


class RecordSubmissionEvidenceCommand(ApplicationCommand):
    """Record human-supplied evidence after an external submission attempt."""

    command_type = "RecordSubmissionEvidence"

    evidence_id: UUID
    submission_package_id: UUID
    evidence_type: Literal["MANUAL_RECEIPT", "MANUAL_PORTAL_REFERENCE"]
    external_reference_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    notes_redacted: str | None = Field(default=None, max_length=1000)

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.platform.events.command_contracts import ApplicationCommand


class PrepareEnterpriseDocumentUploadCommand(ApplicationCommand):
    """Create a server-owned private upload intent before any bytes arrive."""

    command_type = "PrepareEnterpriseDocumentUpload"

    upload_id: UUID
    company_id: UUID
    document_id: UUID
    document_kind: Literal["INSURANCE", "KBIS", "RIB"]
    document_label: str = Field(min_length=1, max_length=240)
    original_filename: str = Field(min_length=1, max_length=500)
    expected_byte_size: int = Field(gt=0, le=2_000_000_000)
    storage_key: str = Field(pattern=r"^[a-f0-9-]{36}/[a-f0-9-]{36}/[a-f0-9-]{36}\.bin$")
    expires_at: datetime

    @model_validator(mode="after")
    def validate_expiry(self) -> PrepareEnterpriseDocumentUploadCommand:
        if self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        return self


class FinalizeEnterpriseDocumentUploadCommand(ApplicationCommand):
    """Materialize a scanned-clean private upload as an immutable enterprise document."""

    command_type = "FinalizeEnterpriseDocumentUpload"

    upload_id: UUID
    company_id: UUID
    document_id: UUID


class VerifyEnterpriseDocumentCommand(ApplicationCommand):
    """Append one human verification decision for a clean enterprise document."""

    command_type = "VerifyEnterpriseDocument"

    company_id: UUID
    document_id: UUID
    expected_verification_revision: int = Field(ge=0)
    outcome: Literal["VALIDATED", "REJECTED"]
    reason_code: Literal[
        "DOCUMENT_ACCEPTED",
        "DOCUMENT_ILLEGIBLE",
        "DOCUMENT_EXPIRED",
        "DOCUMENT_MISMATCH",
        "DOCUMENT_DUPLICATE",
    ]

    @model_validator(mode="after")
    def validate_reason(self) -> VerifyEnterpriseDocumentCommand:
        if self.outcome == "VALIDATED" and self.reason_code != "DOCUMENT_ACCEPTED":
            raise ValueError("validated documents require DOCUMENT_ACCEPTED")
        if self.outcome == "REJECTED" and self.reason_code == "DOCUMENT_ACCEPTED":
            raise ValueError("rejected documents require a rejection reason")
        return self

"""Application commands owned by the DCE module.

Only typed command contracts live here. The authenticated tenant and actor stay
outside the public payload and are supplied by the server-side command context.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApplicationCommand(BaseModel):
    """Closed Pydantic base for an application write intention."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    command_type: ClassVar[str]
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None


class CreateConsultationCommand(ApplicationCommand):
    """Create a buyer consultation and its durable business identity."""

    command_type = "CreateConsultation"

    consultation_id: UUID
    buyer_legal_name: str = Field(min_length=1, max_length=240)
    buyer_normalized_id: str | None = Field(default=None, max_length=120)
    external_reference: str | None = Field(default=None, max_length=240)
    object_label: str = Field(min_length=1, max_length=240)
    location_label: str | None = Field(default=None, max_length=500)
    source_channel: str = Field(min_length=1, max_length=120)
    source_reference: str | None = Field(default=None, max_length=500)
    source_received_at: datetime


class DceDocumentAdmissionInput(BaseModel):
    """References one server-controlled CLEAN staged object for DCE admission."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_id: UUID
    storage_object_id: UUID


class PrepareDceStagingCommand(ApplicationCommand):
    """Create the durable, tenant-scoped intent that precedes a binary upload."""

    command_type = "PrepareDceStaging"

    storage_object_id: UUID
    consultation_id: UUID
    consultation_revision: int = Field(ge=0)
    original_filename: str = Field(min_length=1, max_length=500)
    expected_byte_size: int = Field(gt=0, le=2_000_000_000)
    source_channel: str = Field(
        pattern=r"^(BUYER_PLATFORM|EMAIL|MANUAL_UPLOAD|RECTIFICATION)$"
    )
    expires_at: datetime


class ClaimDceStagedObjectUploadCommand(ApplicationCommand):
    """Atomically reserve one awaiting staged object for a single binary stream."""

    command_type = "ClaimDceStagedObjectUpload"

    storage_object_id: UUID


class RecordDceStagedObjectQuarantineCommand(ApplicationCommand):
    """Trusted server metadata after streamed private write and MIME inspection."""

    command_type = "RecordDceStagedObjectQuarantine"

    storage_object_id: UUID
    actual_byte_size: int = Field(gt=0, le=2_000_000_000)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    media_type: str = Field(min_length=1, max_length=180)
    content_allowed: bool


class RejectDceStagedObjectUploadCommand(ApplicationCommand):
    """Trusted server-only terminal rejection of an object claimed for upload."""

    command_type = "RejectDceStagedObjectUpload"

    storage_object_id: UUID
    rejection_code: str = Field(
        pattern=r"^(UPLOAD_LIMIT_EXCEEDED|STORAGE_WRITE_FAILED|INSPECTION_ERROR|"
        r"MEDIA_TYPE_NOT_ALLOWED|UPLOAD_INTERRUPTED)$"
    )


class ExpireDceStagedObjectCommand(ApplicationCommand):
    """Trusted system-only expiry of a non-consumed staged object."""

    command_type = "ExpireDceStagedObject"

    storage_object_id: UUID


class RecordDceStagedObjectScanCommand(ApplicationCommand):
    """Trusted system-only scan verdict for a quarantined staged object."""

    command_type = "RecordDceStagedObjectScan"

    storage_object_id: UUID
    actual_byte_size: int = Field(gt=0, le=2_000_000_000)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    media_type: str = Field(min_length=1, max_length=180)
    scan_verdict: str = Field(pattern=r"^(CLEAN|INFECTED|ERROR)$")
    scanner_name: str = Field(min_length=1, max_length=120)
    scanner_signature_version: str = Field(min_length=1, max_length=240)
    scanned_at: datetime


class DceExtractionFragmentInput(BaseModel):
    """One bounded, deterministic fragment with a provenance locator."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ordinal: int = Field(gt=0)
    locator_json: dict[str, object]
    text: str = Field(min_length=1, max_length=8_000)
    text_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")


class RecordDceDocumentExtractionCommand(ApplicationCommand):
    """System-only immutable recording of a deterministic document projection."""

    command_type = "RecordDceDocumentExtraction"

    extraction_id: UUID
    dce_document_id: UUID
    input_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    extractor_id: str = Field(min_length=1, max_length=100)
    extractor_version: str = Field(min_length=1, max_length=64)
    status: str = Field(pattern=r"^(COMPLETED|UNSUPPORTED|REJECTED_LIMIT|FAILED_SAFE)$")
    extracted_char_count: int = Field(ge=0, le=10_000_000)
    failure_code: str | None = Field(default=None, max_length=120)
    fragments: list[DceExtractionFragmentInput] = Field(default_factory=list, max_length=500_000)

    @model_validator(mode="after")
    def validate_terminal_projection(self) -> RecordDceDocumentExtractionCommand:
        if self.status == "COMPLETED":
            if self.failure_code is not None or not self.fragments:
                raise ValueError("completed extraction requires fragments and no failure code")
            if sum(len(fragment.text) for fragment in self.fragments) != self.extracted_char_count:
                raise ValueError("completed extraction character count mismatch")
        elif self.failure_code is None or self.fragments or self.extracted_char_count != 0:
            raise ValueError("failed extraction requires a code and no fragments")
        return self


class RegisterDceVersionCommand(ApplicationCommand):
    """Atomically admit an immutable DCE corpus already staged outside HTTP."""

    command_type = "RegisterDceVersion"

    dce_version_id: UUID
    consultation_id: UUID
    consultation_revision: int = Field(ge=0)
    corpus_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    provenance_channel: str = Field(
        pattern=r"^(BUYER_PLATFORM|EMAIL|MANUAL_UPLOAD|RECTIFICATION)$"
    )
    provenance_reference: str | None = Field(default=None, max_length=240)
    provenance_url: str | None = Field(default=None, max_length=2_000)
    source_received_at: datetime
    documents: list[DceDocumentAdmissionInput] = Field(min_length=1)

"""Application commands owned by the DCE module.

Only typed command contracts live here. The authenticated tenant and actor stay
outside the public payload and are supplied by the server-side command context.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    """Metadata for an original already staged by a future secure storage flow."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_id: UUID
    storage_object_id: UUID
    storage_key: str = Field(min_length=1, max_length=1000)
    original_filename: str = Field(min_length=1, max_length=500)
    media_type: str = Field(min_length=1, max_length=180)
    byte_size: int = Field(gt=0, le=2_000_000_000)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    received_from: str = Field(
        pattern=r"^(BUYER_PLATFORM|EMAIL|MANUAL_UPLOAD|RECTIFICATION)$"
    )


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

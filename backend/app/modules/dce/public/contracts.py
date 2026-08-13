"""Stable public HTTP contracts exported by the DCE module."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.dce.application.commands import (
    CreateConsultationCommand,
    RegisterDceVersionCommand,
)


class PublicResponseModel(BaseModel):
    """Closed response base that serializes only explicitly approved fields."""

    model_config = ConfigDict(extra="forbid")


class ProjectionStatusResponse(PublicResponseModel):
    status: Literal["CURRENT", "REFRESH_PENDING", "PARTIAL"]
    refreshed_at: datetime | None = None
    tracking_correlation_id: UUID | None = None


class AggregateReferenceResponse(PublicResponseModel):
    aggregate_type: str
    aggregate_id: UUID
    aggregate_revision: int = Field(ge=0)


class CreateConsultationResponse(PublicResponseModel):
    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["CONSULTATION_CREATED"]
    aggregate_refs: list[AggregateReferenceResponse]
    event_ids: list[UUID]
    projection: ProjectionStatusResponse
    replayed: bool = False


class PrepareDceStagingRequest(BaseModel):
    """Public intent; the server allocates the opaque storage object identity."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    consultation_id: UUID
    consultation_revision: int = Field(ge=0)
    original_filename: str = Field(min_length=1, max_length=500)
    expected_byte_size: int = Field(gt=0, le=2_000_000_000)
    source_channel: str = Field(
        pattern=r"^(BUYER_PLATFORM|EMAIL|MANUAL_UPLOAD|RECTIFICATION)$"
    )
    expires_at: datetime


class DceStagingStatusResponse(PublicResponseModel):
    """Public staging state; intentionally excludes private storage locator data."""

    storage_object_id: UUID
    state: Literal["AWAITING_UPLOAD"]
    expires_at: datetime


class PrepareDceStagingResponse(PublicResponseModel):
    """DCE-STAGING-01 receipt for a server-keyed staging intent."""

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["DCE_STAGING_PREPARED"]
    aggregate_refs: list[AggregateReferenceResponse]
    event_ids: list[UUID]
    staging: DceStagingStatusResponse
    replayed: bool = False


class UploadDceStagedObjectResponse(PublicResponseModel):
    """Safe DCE-UPLOAD-01 success response without storage or scanner internals."""

    storage_object_id: UUID
    state: Literal["CLEAN"]


class RegisterDceVersionResponse(PublicResponseModel):
    """DCE-ADMIT-HTTP-01 success receipt without document or storage metadata."""

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["DCE_VERSION_REGISTERED"]
    aggregate_refs: list[AggregateReferenceResponse]
    event_ids: list[UUID]
    replayed: bool = False


class DceVersionMetadataResponse(PublicResponseModel):
    """DCE-READ-01 metadata only; it deliberately excludes documents and provenance."""

    id: UUID
    consultation_id: UUID
    predecessor_dce_version_id: UUID | None
    source_received_at: datetime
    lifecycle: str
    integrity: str
    classification_readiness: str
    analysis_readiness: str
    aggregate_revision: int = Field(ge=0)


class ConsultationProjectionResponse(PublicResponseModel):
    id: UUID
    buyer_legal_name: str
    external_reference: str | None
    object_label: str
    location_label: str | None
    lifecycle: str
    freshness: str
    aggregate_revision: int = Field(ge=0)
    lots: list[str]
    tranches: list[str]
    projection_status: Literal["CURRENT", "REFRESH_PENDING", "PARTIAL"]


CreateConsultationRequest = CreateConsultationCommand
RegisterDceVersionRequest = RegisterDceVersionCommand

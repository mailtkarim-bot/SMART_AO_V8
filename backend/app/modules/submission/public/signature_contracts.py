from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RequestSubmissionSignatureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    signature_id: UUID
    expected_package_version: int = Field(ge=1)


class RecordSubmissionSignatureCallbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_id: UUID
    submission_package_id: UUID
    provider: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z][A-Z0-9_.-]+$")
    provider_reference_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    signature_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    outcome: Literal["SIGNED", "REJECTED"]


class SubmissionSignatureCommandResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal[
        "SUBMISSION_SIGNATURE_REQUESTED",
        "SUBMISSION_SIGNATURE_RECORDED",
    ]
    aggregate_refs: list[dict[str, object]]
    event_ids: list[UUID]
    external_submission: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    replayed: bool = False


class SubmissionSignatureProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signature_id: UUID
    submission_package_id: UUID
    case_id: UUID
    provider: str
    status: Literal["REQUESTED", "SIGNED", "REJECTED"]
    expected_package_version: int
    revision: Literal[1, 2]
    external_submission: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"

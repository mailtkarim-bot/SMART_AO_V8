from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RecordSubmissionEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    evidence_id: UUID
    evidence_type: Literal["MANUAL_RECEIPT", "MANUAL_PORTAL_REFERENCE"]
    external_reference_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    notes_redacted: str | None = Field(default=None, max_length=1000)


class SubmissionEvidenceCommandResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["SUBMISSION_EVIDENCE_RECORDED"]
    aggregate_refs: list[dict[str, object]]
    event_ids: list[UUID]
    external_submission: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    replayed: bool = False

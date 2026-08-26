from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PreparationCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None


class EvaluatePreparationReadinessRequest(PreparationCommandRequest):
    expected_revision: int = Field(ge=0)
    package_id: UUID
    assignment_id: UUID
    dce_version_id: UUID


class GenerateTechnicalDocumentRequest(PreparationCommandRequest):
    expected_revision: int = Field(ge=0)
    readiness_revision: int = Field(ge=1)
    document_kind: Literal["TECHNICAL_RESPONSE", "DC1", "DC2", "DC4"]


class RequestPreparationReviewRequest(PreparationCommandRequest):
    expected_package_revision: int = Field(ge=0)
    review_id: UUID
    target_document_id: UUID
    target_version: int = Field(gt=0)


class DecidePreparationReviewRequest(PreparationCommandRequest):
    expected_review_revision: int = Field(ge=1)
    review_id: UUID
    target_document_id: UUID
    decision_code: Literal["ACCEPTED", "CORRECTIONS_REQUIRED", "REJECTED"]
    decision_note: str | None = Field(default=None, max_length=2000)


class AddPreparationCorrectionRequest(PreparationCommandRequest):
    review_id: UUID
    target_document_id: UUID
    correction_code: Literal[
        "SOURCE_MISSING", "SOURCE_WRONG", "SECTION_INCOMPLETE", "WORDING_UNCLEAR"
    ]
    instruction: str = Field(min_length=1, max_length=2000)
    source_locator: str | None = Field(default=None, max_length=500)


class CreatePreparationSnapshotRequest(PreparationCommandRequest):
    expected_package_revision: int = Field(ge=0)
    package_id: UUID
    snapshot_id: UUID


class TransmitPreparationSnapshotRequest(PreparationCommandRequest):
    expected_package_revision: int = Field(ge=0)
    package_id: UUID
    snapshot_id: UUID
    transmission_id: UUID


class CreateTechnicalResponseDraftRequest(PreparationCommandRequest):
    expected_package_revision: int = Field(ge=0)
    draft_id: UUID
    source_document_id: UUID
    section_codes: list[str] = Field(min_length=1, max_length=32)
    source_refs: list[UUID] = Field(min_length=1, max_length=64)


class PreparationAggregateReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aggregate_type: Literal[
        "PreparationPackage",
        "GeneratedTechnicalDocument",
        "PreparationReview",
        "TechnicalResponseDraft",
        "PreparationSnapshot",
        "PreparationTransmission",
    ]
    aggregate_id: UUID
    aggregate_revision: int = Field(ge=0)


class PreparationCommandResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal[
        "PREPARATION_READINESS_EVALUATED",
        "TECHNICAL_DOCUMENT_GENERATED",
        "CONTROLLED_DRAFT_GENERATED",
        "PREPARATION_REVIEW_REQUESTED",
        "PREPARATION_REVIEW_DECIDED",
        "PREPARATION_CORRECTION_ADDED",
        "TECHNICAL_RESPONSE_DRAFT_CREATED",
        "PREPARATION_SNAPSHOT_CREATED",
        "PREPARATION_TRANSMITTED_TO_PATRON",
    ]
    aggregate_refs: list[PreparationAggregateReference]
    event_ids: list[UUID]
    replayed: bool = False


class PreparationReadinessProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_id: UUID
    revision: int = Field(ge=1)
    state: Literal["READY", "READY_WITH_WARNINGS", "BLOCKED"]
    blocker_codes: list[str]
    warning_codes: list[str]
    checked_requirement_count: int = Field(ge=0)
    checked_task_count: int = Field(ge=0)


class GeneratedDocumentProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    version: int = Field(ge=1)
    document_kind: Literal["TECHNICAL_RESPONSE", "DC1", "DC2", "DC4"]
    state: Literal["GENERATED", "FAILED_SAFE"]
    readiness_revision: int = Field(ge=1)


class PreparationPackageProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: UUID
    case_id: UUID
    assignment_id: UUID
    dce_version_id: UUID
    state: Literal["IN_PREPARATION", "A_REVIEW", "READY", "BLOCKED", "GENERATED"]
    aggregate_revision: int = Field(ge=0)
    latest_readiness: PreparationReadinessProjection | None
    generated_documents: list[GeneratedDocumentProjection]

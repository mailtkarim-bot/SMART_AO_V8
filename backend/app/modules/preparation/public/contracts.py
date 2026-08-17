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
    document_kind: Literal["TECHNICAL_RESPONSE"]


class PreparationAggregateReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aggregate_type: Literal["PreparationPackage", "GeneratedTechnicalDocument"]
    aggregate_id: UUID
    aggregate_revision: int = Field(ge=0)


class PreparationCommandResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["PREPARATION_READINESS_EVALUATED", "TECHNICAL_DOCUMENT_GENERATED"]
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
    document_kind: Literal["TECHNICAL_RESPONSE"]
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

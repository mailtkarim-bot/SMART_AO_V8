from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PricingImportRowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_number: int = Field(ge=1)
    code: str | None
    designation: str | None
    unit: str | None
    quantity_decimal: str | None
    unit_price_minor: int | None
    total_minor: int | None
    errors: list[str]


class PricingImportAggregateReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aggregate_type: str
    aggregate_id: UUID
    aggregate_revision: int = Field(ge=1)


class CommitPricingImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    report_id: UUID
    expected_batch_revision: int = Field(gt=0)
    expected_report_revision: int = Field(ge=0)


class PricingImportCommitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["PRICING_IMPORT_COMMITTED"]
    aggregate_refs: list[PricingImportAggregateReferenceResponse]
    event_ids: list[UUID]
    replayed: bool = False


class PricingImportPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: UUID
    document_kind: Literal["DPGF", "BPU", "EXCEL"]
    filename: str
    row_count: int = Field(ge=0)
    valid_row_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    total_minor: int = Field(ge=0)
    rows: list[PricingImportRowResponse]

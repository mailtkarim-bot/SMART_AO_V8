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


class PricingImportCreationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None


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


class PricingImportBatchReadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: UUID
    case_id: UUID
    document_kind: Literal["DPGF", "BPU", "EXCEL"]
    state: Literal["PREVIEWED", "COMMITTED"]
    aggregate_revision: int = Field(ge=1)
    row_count: int = Field(ge=0)
    valid_row_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    total_minor: int = Field(ge=0)
    rows: list[PricingImportRowResponse]


class PricingImportPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: UUID
    document_kind: Literal["DPGF", "BPU", "EXCEL"]
    filename: str
    row_count: int = Field(ge=0)
    valid_row_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    total_minor: int = Field(ge=0)
    truncated: bool = Field(default=False)
    limit_reason: Literal["ROW_LIMIT", "ERROR_LIMIT"] | None = Field(default=None)
    rows: list[PricingImportRowResponse]
    batch_id: UUID | None = None
    state: Literal["PREVIEWED"] | None = None
    aggregate_revision: int | None = Field(default=None, ge=1)
    result_code: Literal["PRICING_IMPORT_PREVIEWED"] | None = None
    command_id: UUID | None = None
    idempotency_key: UUID | None = None
    event_ids: list[UUID] = Field(default_factory=list)
    replayed: bool = False

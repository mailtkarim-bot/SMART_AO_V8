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

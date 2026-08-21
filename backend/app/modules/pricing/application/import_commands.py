from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.platform.events.command_contracts import ApplicationCommand


class CreatePricingImportRowCommand(BaseModel):
    """One normalized row produced by the server-side preview validator."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    row_number: int = Field(ge=1)
    code: str | None = None
    designation: str | None = None
    unit: str | None = None
    quantity_decimal: str | None = Field(
        default=None,
        pattern=r"^(0|[1-9][0-9]*)(\.[0-9]+)?$",
    )
    unit_price_minor: int | None = Field(default=None, ge=0)
    total_minor: int | None = Field(default=None, ge=0)
    errors: list[str] = Field(default_factory=list)


class CreatePricingImportPreviewCommand(ApplicationCommand):
    """Persist a validated, normalized pricing preview without the source file."""

    command_type = "CreatePricingImportPreview"

    case_id: UUID
    document_kind: Literal["DPGF", "BPU", "EXCEL"]
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    rows: list[CreatePricingImportRowCommand] = Field(max_length=100)


class CommitPricingImportCommand(ApplicationCommand):
    """Apply one validated normalized import batch to a financial draft."""

    command_type = "CommitPricingImport"

    batch_id: UUID
    case_id: UUID
    report_id: UUID
    expected_batch_revision: int = Field(gt=0)
    expected_report_revision: int = Field(ge=0)

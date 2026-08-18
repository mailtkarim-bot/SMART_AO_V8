from uuid import UUID

from pydantic import Field

from app.platform.events.command_contracts import ApplicationCommand


class CommitPricingImportCommand(ApplicationCommand):
    """Apply one validated normalized import batch to a financial draft."""

    command_type = "CommitPricingImport"

    batch_id: UUID
    case_id: UUID
    report_id: UUID
    expected_batch_revision: int = Field(gt=0)
    expected_report_revision: int = Field(ge=0)

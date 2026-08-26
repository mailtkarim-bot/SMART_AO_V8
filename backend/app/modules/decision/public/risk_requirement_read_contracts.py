from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DecisionRiskRequirementLinkItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link_id: UUID
    case_id: UUID
    risk_id: UUID
    requirement_id: UUID
    dce_version_id: UUID
    relationship: str
    rationale: str
    source_refs: tuple[str, ...]
    created_at: datetime
    action_id: UUID | None
    action_state: str | None
    action_severity: str | None
    action_revision: int | None


class DecisionRiskRequirementPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DecisionRiskRequirementLinkItem]
    next_cursor: str | None


class DecisionPricingReconciliationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link_id: UUID
    batch_id: UUID
    document_kind: str
    batch_state: str
    row_number: int
    code: str | None
    designation: str | None
    unit: str | None
    match_basis: str
    verification_status: str


class DecisionPricingReconciliationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link_id: UUID
    search: str
    items: list[DecisionPricingReconciliationItem]


class DecisionCctpPricingCrossingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dce_version_id: UUID
    source_fragment_id: UUID
    source_locator_label: str
    source_start_byte_offset: int
    source_end_byte_offset: int
    batch_id: UUID
    document_kind: str
    row_number: int
    code: str | None
    designation: str | None
    unit: str | None
    match_score_bps: int
    match_basis: str
    verification_status: str


class DecisionCctpPricingCrossingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: UUID
    items: list[DecisionCctpPricingCrossingItem]


class DecisionDocumentContradictionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contradiction_id: UUID
    dce_version_id: UUID
    contradiction_type: str
    source_fragment_id: UUID
    source_locator_label: str
    source_start_byte_offset: int
    source_end_byte_offset: int
    related_batch_id: UUID
    related_document_kind: str
    related_row_number: int
    related_code: str | None
    related_designation: str | None
    related_unit: str | None
    comparison_basis: str
    verification_status: str


class DecisionDocumentContradictionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: UUID
    items: list[DecisionDocumentContradictionItem]

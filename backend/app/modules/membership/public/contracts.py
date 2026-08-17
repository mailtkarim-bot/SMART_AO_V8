"""Closed HTTP projections for collaborator Assignment history reads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssignmentHistoryItemResponse(PublicResponseModel):
    record_id: UUID
    kind: Literal["ACKNOWLEDGEMENT", "CLARIFICATION_REQUEST", "UNAVAILABILITY_REPORT"]
    recorded_at: datetime
    assignment_revision: int | None = Field(default=None, ge=0)
    operational_state: Literal["RECORDED", "OPEN"]
    clarification_kind: Literal[
        "SCOPE",
        "PRIORITY",
        "DEADLINE",
        "DOCUMENT",
        "RESPONSIBILITY",
        "OTHER",
    ] | None = None
    priority: Literal["LOW", "NORMAL", "HIGH"] | None = None
    reason_kind: Literal[
        "SICKNESS",
        "LEAVE",
        "CAPACITY_CONFLICT",
        "SKILL_GAP",
        "ACCESS_PROBLEM",
        "OTHER",
    ] | None = None
    unavailable_from: datetime | None = None
    unavailable_until: datetime | None = None
    known_deadline_impact: bool | None = None


class AssignmentHistoryResponse(PublicResponseModel):
    assignment_id: UUID
    case_id: UUID
    case_lifecycle: str
    items: list[AssignmentHistoryItemResponse]


PatronAssignmentScopeAction = Literal[
    "case.dce.read",
    "dce.requirement.confirm",
    "document.administrative.read",
    "preparation.transmit",
    "assignment.acknowledge",
    "assignment.clarify",
    "assignment.history.read",
    "assignment.unavailability",
]
PatronAssignmentState = Literal["ACTIVE", "SUSPENDED", "ENDED", "EXPIRED"]
PatronCaseLifecycle = Literal["ACTIVE", "STOPPED", "ARCHIVED"]
PatronAssignmentJournalEventType = Literal[
    "ASSIGNMENT_CREATED",
    "ASSIGNMENT_SCOPE_AMENDED",
    "ASSIGNMENT_SUSPENDED",
    "ASSIGNMENT_REACTIVATED",
    "ASSIGNMENT_ENDED",
]
PatronAssignmentReasonCode = Literal[
    "PATRON_SUSPENDED",
    "WORKLOAD_REALLOCATION",
    "CASE_PAUSED",
    "ACCESS_REVIEW",
    "PATRON_ENDED",
    "CASE_STOPPED",
    "CASE_ARCHIVED",
    "COLLABORATOR_UNAVAILABLE",
    "MEMBERSHIP_REVOKED",
    "PATRON_REACTIVATED",
    "CASE_RESUMED",
    "ACCESS_REVIEW_CLEARED",
]


class PatronAssignmentCockpitItemResponse(PublicResponseModel):
    assignment_id: UUID
    case_id: UUID
    case_title: str
    case_lifecycle: PatronCaseLifecycle
    state: PatronAssignmentState
    aggregate_revision: int = Field(ge=0)
    starts_at: datetime
    ends_at: datetime | None = None
    ended_at: datetime | None = None
    scope_actions: list[PatronAssignmentScopeAction]
    scope_classifications: list[Literal["INTERNAL_OPERATIONAL"]]


class PatronAssignmentCockpitListResponse(PublicResponseModel):
    items: list[PatronAssignmentCockpitItemResponse]


class PatronAssignmentJournalItemResponse(PublicResponseModel):
    record_id: UUID
    recorded_at: datetime
    event_type: PatronAssignmentJournalEventType
    previous_revision: int | None = Field(default=None, ge=0)
    resulting_revision: int = Field(ge=0)
    previous_state: PatronAssignmentState | None = None
    resulting_state: PatronAssignmentState
    reason_code: PatronAssignmentReasonCode | None = None
    previous_scope_actions: list[PatronAssignmentScopeAction] | None = None
    previous_scope_classifications: list[Literal["INTERNAL_OPERATIONAL"]] | None = None
    resulting_scope_actions: list[PatronAssignmentScopeAction]
    resulting_scope_classifications: list[Literal["INTERNAL_OPERATIONAL"]]


class PatronAssignmentJournalResponse(PublicResponseModel):
    assignment: PatronAssignmentCockpitItemResponse
    items: list[PatronAssignmentJournalItemResponse]


PatronAssignmentInteractionKind = Literal[
    "ACKNOWLEDGEMENT",
    "CLARIFICATION_REQUEST",
    "UNAVAILABILITY_REPORT",
]


class PatronAssignmentInteractionItemResponse(PublicResponseModel):
    record_id: UUID
    kind: PatronAssignmentInteractionKind
    recorded_at: datetime
    assignment_revision: int | None = Field(default=None, ge=0)
    operational_state: Literal["RECORDED", "OPEN"]
    clarification_kind: Literal[
        "SCOPE",
        "PRIORITY",
        "DEADLINE",
        "DOCUMENT",
        "RESPONSIBILITY",
        "OTHER",
    ] | None = None
    priority: Literal["LOW", "NORMAL", "HIGH"] | None = None
    reason_kind: Literal[
        "SICKNESS",
        "LEAVE",
        "CAPACITY_CONFLICT",
        "SKILL_GAP",
        "ACCESS_PROBLEM",
        "OTHER",
    ] | None = None
    unavailable_from: datetime | None = None
    unavailable_until: datetime | None = None
    known_deadline_impact: bool | None = None


class PatronAssignmentInteractionsResponse(PublicResponseModel):
    assignment_id: UUID
    case_id: UUID
    case_lifecycle: PatronCaseLifecycle
    items: list[PatronAssignmentInteractionItemResponse]


FinancialReportCategory = Literal[
    "SALES",
    "DIRECT_COST",
    "OVERHEAD",
    "SUBCONTRACTING",
    "CONTINGENCY",
    "GROSS_MARGIN",
    "FORECAST_CASHFLOW",
]


class PatronFinancialReportLineResponse(PublicResponseModel):
    line_id: UUID
    category: FinancialReportCategory
    label: str
    quantity_decimal: str
    unit: str
    amount_minor: int
    currency_code: str


class PatronFinancialReportSummaryResponse(PublicResponseModel):
    sales_total_minor: int
    direct_cost_total_minor: int
    overhead_total_minor: int
    subcontracting_total_minor: int
    contingency_total_minor: int
    gross_margin_minor: int
    gross_margin_rate_bps: int
    forecast_cashflow_minor: int


class PatronFinancialReportResponse(PublicResponseModel):
    report_id: UUID
    case_id: UUID
    status: Literal["PUBLISHED"]
    currency_code: str
    calculated_at: datetime
    ruleset_version: int = Field(ge=1)
    summary: PatronFinancialReportSummaryResponse
    lines: list[PatronFinancialReportLineResponse]


class PatronFinancialReportDraftResponse(PublicResponseModel):
    """Closed patron-only projection of one mutable financial DRAFT."""

    report_id: UUID
    case_id: UUID
    status: Literal["DRAFT"]
    aggregate_revision: int = Field(ge=0)
    currency_code: str
    calculated_at: datetime
    ruleset_version: int = Field(ge=1)
    summary: PatronFinancialReportSummaryResponse
    lines: list[PatronFinancialReportLineResponse]

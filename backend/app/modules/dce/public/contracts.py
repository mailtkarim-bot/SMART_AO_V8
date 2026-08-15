"""Stable public HTTP contracts exported by the DCE module."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.modules.dce.application.commands import (
    AcknowledgeAssignmentCommand,
    AmendCaseAssignmentScopeCommand,
    AssignmentInteractionKind,
    AssignmentInteractionValidationCode,
    AssignmentScopeAction,
    AssignmentScopeClassification,
    CreateCaseAssignmentCommand,
    CreateConsultationCommand,
    EndCaseAssignmentCommand,
    EndReasonCode,
    PublishFinancialReportCommand,
    ReactivateCaseAssignmentCommand,
    ReactivationReasonCode,
    RecordDceRequirementConfirmationCommand,
    RegisterDceVersionCommand,
    ReportAssignmentUnavailabilityCommand,
    RequestAssignmentClarificationCommand,
    SuspendCaseAssignmentCommand,
    SuspensionReasonCode,
    ValidateAssignmentInteractionCommand,
)


class PublicResponseModel(BaseModel):
    """Closed response base that serializes only explicitly approved fields."""

    model_config = ConfigDict(extra="forbid")


class PublicRequestModel(BaseModel):
    """Closed HTTP intent model; server-owned actor and tenant stay outside it."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProjectionStatusResponse(PublicResponseModel):
    status: Literal["CURRENT", "REFRESH_PENDING", "PARTIAL"]
    refreshed_at: datetime | None = None
    tracking_correlation_id: UUID | None = None


class AggregateReferenceResponse(PublicResponseModel):
    aggregate_type: str
    aggregate_id: UUID
    aggregate_revision: int = Field(ge=0)


class CreateConsultationResponse(PublicResponseModel):
    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["CONSULTATION_CREATED"]
    aggregate_refs: list[AggregateReferenceResponse]
    event_ids: list[UUID]
    projection: ProjectionStatusResponse
    replayed: bool = False


class PrepareDceStagingRequest(BaseModel):
    """Public intent; the server allocates the opaque storage object identity."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    consultation_id: UUID
    consultation_revision: int = Field(ge=0)
    original_filename: str = Field(min_length=1, max_length=500)
    expected_byte_size: int = Field(gt=0, le=2_000_000_000)
    source_channel: str = Field(
        pattern=r"^(BUYER_PLATFORM|EMAIL|MANUAL_UPLOAD|RECTIFICATION)$"
    )
    expires_at: datetime


class DceStagingStatusResponse(PublicResponseModel):
    """Public staging state; intentionally excludes private storage locator data."""

    storage_object_id: UUID
    state: Literal["AWAITING_UPLOAD"]
    expires_at: datetime


class PrepareDceStagingResponse(PublicResponseModel):
    """DCE-STAGING-01 receipt for a server-keyed staging intent."""

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["DCE_STAGING_PREPARED"]
    aggregate_refs: list[AggregateReferenceResponse]
    event_ids: list[UUID]
    staging: DceStagingStatusResponse
    replayed: bool = False


class UploadDceStagedObjectResponse(PublicResponseModel):
    """Safe DCE-UPLOAD-01 success response without storage or scanner internals."""

    storage_object_id: UUID
    state: Literal["CLEAN"]


class RegisterDceVersionResponse(PublicResponseModel):
    """DCE-ADMIT-HTTP-01 success receipt without document or storage metadata."""

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["DCE_VERSION_REGISTERED"]
    aggregate_refs: list[AggregateReferenceResponse]
    event_ids: list[UUID]
    replayed: bool = False


class DceVersionMetadataResponse(PublicResponseModel):
    """DCE-READ-01 metadata only; it deliberately excludes documents and provenance."""

    id: UUID
    consultation_id: UUID
    predecessor_dce_version_id: UUID | None
    source_received_at: datetime
    lifecycle: str
    integrity: str
    classification_readiness: str
    analysis_readiness: str
    aggregate_revision: int = Field(ge=0)


class ConsultationProjectionResponse(PublicResponseModel):
    id: UUID
    buyer_legal_name: str
    external_reference: str | None
    object_label: str
    location_label: str | None
    lifecycle: str
    freshness: str
    aggregate_revision: int = Field(ge=0)
    lots: list[str]
    tranches: list[str]
    projection_status: Literal["CURRENT", "REFRESH_PENDING", "PARTIAL"]


class CaseDceReadingDceResponse(PublicResponseModel):
    dce_version_id: UUID
    lifecycle: str
    integrity: str
    classification_readiness: str
    analysis_readiness: str
    source_received_at: datetime


class CaseDceReadingCountersResponse(PublicResponseModel):
    total: int = Field(ge=0)
    pending_human_confirmation: int = Field(ge=0)
    confirmed: int = Field(ge=0)
    review_required: int = Field(ge=0)
    not_applicable: int = Field(ge=0)


class CaseDceReadingRequirementResponse(PublicResponseModel):
    requirement_id: UUID
    requirement_type: str
    directive_signal: str
    confirmation_outcome: str
    uncertainty_status: str
    document_family: str
    source_locator_label: str


class CaseDceReadingResponse(PublicResponseModel):
    case_id: UUID
    work_label: str
    case_lifecycle: str
    commercial_stage: str
    dce_freshness: str
    availability: Literal["AVAILABLE"]
    dce: CaseDceReadingDceResponse
    counters: CaseDceReadingCountersResponse
    requirements: list[CaseDceReadingRequirementResponse]


class AssignedCaseResponse(PublicResponseModel):
    """Closed Case list item returned after server-side ReBAC filtering."""

    case_id: UUID
    work_label: str
    case_lifecycle: str
    commercial_stage: str
    dce_availability: str


class AcknowledgeAssignmentRequest(PublicRequestModel):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    expected_revision: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=500)

    def to_command(self, *, assignment_id: UUID) -> AcknowledgeAssignmentCommand:
        return AcknowledgeAssignmentCommand(
            **self.model_dump(),
            assignment_id=assignment_id,
        )


class RequestAssignmentClarificationRequest(PublicRequestModel):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    expected_revision: int = Field(ge=0)
    clarification_kind: Literal[
        "SCOPE",
        "PRIORITY",
        "DEADLINE",
        "DOCUMENT",
        "RESPONSIBILITY",
        "OTHER",
    ]
    subject: str = Field(min_length=1, max_length=160)
    question: str = Field(min_length=1, max_length=2_000)
    requested_scope: str | None = Field(default=None, max_length=500)
    priority: Literal["LOW", "NORMAL", "HIGH"] = "NORMAL"

    def to_command(
        self,
        *,
        assignment_id: UUID,
    ) -> RequestAssignmentClarificationCommand:
        return RequestAssignmentClarificationCommand(
            **self.model_dump(),
            assignment_id=assignment_id,
        )


class ReportAssignmentUnavailabilityRequest(PublicRequestModel):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    expected_revision: int = Field(ge=0)
    reason_kind: Literal[
        "SICKNESS",
        "LEAVE",
        "CAPACITY_CONFLICT",
        "SKILL_GAP",
        "ACCESS_PROBLEM",
        "OTHER",
    ]
    reason: str = Field(min_length=1, max_length=2_000)
    unavailable_from: datetime
    unavailable_until: datetime | None = None
    known_deadline_impact: bool = False
    impact_note: str | None = Field(default=None, max_length=500)

    def to_command(
        self,
        *,
        assignment_id: UUID,
    ) -> ReportAssignmentUnavailabilityCommand:
        return ReportAssignmentUnavailabilityCommand(
            **self.model_dump(),
            assignment_id=assignment_id,
        )


class AssignmentCommandResponse(PublicResponseModel):
    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal[
        "ASSIGNMENT_ACKNOWLEDGED",
        "ASSIGNMENT_CLARIFICATION_REQUESTED",
        "ASSIGNMENT_UNAVAILABILITY_REPORTED",
        "CASE_ASSIGNMENT_CREATED",
        "CASE_ASSIGNMENT_SCOPE_AMENDED",
        "CASE_ASSIGNMENT_SUSPENDED",
        "CASE_ASSIGNMENT_REACTIVATED",
        "CASE_ASSIGNMENT_ENDED",
        "INTERACTION_VALIDATED",
    ]
    aggregate_refs: list[AggregateReferenceResponse]
    event_ids: list[UUID]
    replayed: bool = False


class PublishFinancialReportRequest(PublicRequestModel):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    expected_revision: int = Field(ge=0)

    def to_command(self, *, case_id: UUID, report_id: UUID) -> PublishFinancialReportCommand:
        return PublishFinancialReportCommand(
            **self.model_dump(),
            case_id=case_id,
            report_id=report_id,
        )


class FinancialReportPublicationResponse(PublicResponseModel):
    """Closed receipt intentionally excluding every financial value and source."""

    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["FINANCIAL_REPORT_PUBLISHED"]
    aggregate_refs: list[AggregateReferenceResponse]
    event_ids: list[UUID]
    replayed: bool = False


class PatronAssignmentScopeRequest(PublicRequestModel):
    """Closed operational scope intentionally excluding all pricing and decision actions."""

    scope_actions: list[AssignmentScopeAction] = Field(min_length=1, max_length=8)
    scope_classifications: list[AssignmentScopeClassification] = Field(min_length=1, max_length=1)

    @model_validator(mode="after")
    def validate_and_canonicalize_scope(self) -> PatronAssignmentScopeRequest:
        if len(self.scope_actions) != len(set(self.scope_actions)):
            raise ValueError("assignment scope actions must not contain duplicates")
        if len(self.scope_classifications) != len(set(self.scope_classifications)):
            raise ValueError("assignment scope classifications must not contain duplicates")
        self.scope_actions.sort()
        self.scope_classifications.sort()
        return self


class CreatePatronCaseAssignmentRequest(PatronAssignmentScopeRequest):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    assignment_id: UUID
    target_membership_id: UUID
    expected_case_revision: int = Field(ge=0)
    starts_at: AwareDatetime
    ends_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_period(self) -> CreatePatronCaseAssignmentRequest:
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("assignment period must be strictly ordered")
        return self

    def to_command(self, *, case_id: UUID) -> CreateCaseAssignmentCommand:
        return CreateCaseAssignmentCommand(**self.model_dump(), case_id=case_id)


class AmendPatronAssignmentScopeRequest(PatronAssignmentScopeRequest):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    expected_revision: int = Field(ge=0)

    def to_command(self, *, assignment_id: UUID) -> AmendCaseAssignmentScopeCommand:
        return AmendCaseAssignmentScopeCommand(**self.model_dump(), assignment_id=assignment_id)


class SuspendPatronCaseAssignmentRequest(PublicRequestModel):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    expected_revision: int = Field(ge=0)
    suspension_reason_code: SuspensionReasonCode

    def to_command(self, *, assignment_id: UUID) -> SuspendCaseAssignmentCommand:
        return SuspendCaseAssignmentCommand(**self.model_dump(), assignment_id=assignment_id)


class ReactivatePatronCaseAssignmentRequest(PublicRequestModel):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    expected_revision: int = Field(ge=0)
    reactivation_reason_code: ReactivationReasonCode

    def to_command(self, *, assignment_id: UUID) -> ReactivateCaseAssignmentCommand:
        return ReactivateCaseAssignmentCommand(**self.model_dump(), assignment_id=assignment_id)


class EndPatronCaseAssignmentRequest(PublicRequestModel):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    expected_revision: int = Field(ge=0)
    end_reason_code: EndReasonCode

    def to_command(self, *, assignment_id: UUID) -> EndCaseAssignmentCommand:
        return EndCaseAssignmentCommand(**self.model_dump(), assignment_id=assignment_id)


class ValidatePatronAssignmentInteractionRequest(PublicRequestModel):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    interaction_id: UUID
    interaction_kind: AssignmentInteractionKind
    validation_code: AssignmentInteractionValidationCode

    @model_validator(mode="after")
    def validate_kind_code_pair(self) -> ValidatePatronAssignmentInteractionRequest:
        expected = {
            "ACKNOWLEDGEMENT": "ACKNOWLEDGEMENT_NOTED",
            "CLARIFICATION_REQUEST": "CLARIFICATION_NOTED",
            "UNAVAILABILITY_REPORT": "UNAVAILABILITY_NOTED",
        }[self.interaction_kind]
        if self.validation_code != expected:
            raise ValueError("interaction validation code must match interaction kind")
        return self

    def to_command(self, *, assignment_id: UUID) -> ValidateAssignmentInteractionCommand:
        return ValidateAssignmentInteractionCommand(
            **self.model_dump(),
            assignment_id=assignment_id,
        )


class RecordDceRequirementConfirmationRequest(PublicResponseModel):
    """Untrusted HTTP intent; scope and actor stay server-resolved."""

    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    confirmation_id: UUID
    expected_confirmation_revision: int = Field(ge=0)
    outcome: Literal["CONFIRMED", "REVIEW_REQUIRED", "NOT_APPLICABLE"]
    reason_code: Literal[
        "SOURCE_REVIEWED",
        "AMBIGUOUS_SOURCE",
        "CONTRADICTORY_DCE",
        "PATRON_NOT_APPLICABLE",
        "NEEDS_EXTERNAL_CLARIFICATION",
    ]

    def to_command(
        self,
        *,
        requirement_id: UUID,
    ) -> RecordDceRequirementConfirmationCommand:
        return RecordDceRequirementConfirmationCommand(
            **self.model_dump(),
            requirement_id=requirement_id,
        )


class RecordDceRequirementConfirmationResponse(PublicResponseModel):
    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: Literal["DCE_REQUIREMENT_CONFIRMED"]
    aggregate_refs: list[AggregateReferenceResponse]
    event_ids: list[UUID]
    replayed: bool = False


CreateConsultationRequest = CreateConsultationCommand
RegisterDceVersionRequest = RegisterDceVersionCommand

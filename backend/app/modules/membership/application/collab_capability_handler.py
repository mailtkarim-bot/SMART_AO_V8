from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.dce.infrastructure.models.dce_requirements import DceRequirementRecord
from app.modules.enterprise.infrastructure.models import (
    CaseCapabilityGapRecord,
    CaseCapabilityProposalRecord,
    EnterpriseCapabilityRecord,
    EnterpriseCapabilityVersionRecord,
)
from app.modules.membership.application.collab_capability_commands import (
    ProposeCapabilityForCaseCommand,
    ReportCapabilityGapCommand,
)
from app.modules.membership.infrastructure.records import (
    CaseAssignmentRecord,
    CollaboratorTaskRecord,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandExecutionError,
    CommandHandler,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.security.capabilities import Capability


def _require_active_assignment(
    session: Session,
    *,
    context: CommandContext,
    case_id: UUID,
    assignment_id: UUID,
    required_action: Capability,
) -> CaseAssignmentRecord:
    if context.membership_id is None:
        raise CommandExecutionError("ASSIGNMENT_REQUIRED")
    assignment = session.scalar(
        sa.select(CaseAssignmentRecord).where(
            CaseAssignmentRecord.tenant_id == context.tenant_id,
            CaseAssignmentRecord.id == assignment_id,
            CaseAssignmentRecord.case_id == case_id,
            CaseAssignmentRecord.membership_id == context.membership_id,
            CaseAssignmentRecord.state == "ACTIVE",
            CaseAssignmentRecord.starts_at <= context.received_at,
            sa.or_(
                CaseAssignmentRecord.ends_at.is_(None),
                CaseAssignmentRecord.ends_at > context.received_at,
            ),
        )
    )
    if assignment is None:
        raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
    if required_action.value not in assignment.scope_actions_json:
        raise CommandExecutionError("SCOPE_DENIED")
    return assignment


def _validate_source(
    session: Session,
    *,
    tenant_id: UUID,
    case_id: UUID,
    assignment_id: UUID,
    requirement_id: UUID | None,
    task_id: UUID | None,
) -> None:
    if requirement_id is None and task_id is None:
        raise CommandExecutionError("CAPABILITY_SOURCE_REQUIRED")
    if requirement_id is not None:
        requirement = session.scalar(
            sa.select(DceRequirementRecord).where(
                DceRequirementRecord.tenant_id == tenant_id,
                DceRequirementRecord.id == requirement_id,
            )
        )
        if requirement is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
    if task_id is not None:
        task = session.scalar(
            sa.select(CollaboratorTaskRecord).where(
                CollaboratorTaskRecord.tenant_id == tenant_id,
                CollaboratorTaskRecord.id == task_id,
                CollaboratorTaskRecord.case_id == case_id,
                CollaboratorTaskRecord.assignment_id == assignment_id,
            )
        )
        if task is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")


class ProposeCapabilityForCaseHandler:
    def execute(
        self,
        *,
        session: Session,
        command: ProposeCapabilityForCaseCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        tenant_id = UUID(str(context.tenant_id))
        _require_active_assignment(
            session,
            context=context,
            case_id=command.case_id,
            assignment_id=command.assignment_id,
            required_action=Capability.PREPARATION_CAPABILITY_PROPOSE,
        )
        _validate_source(
            session,
            tenant_id=tenant_id,
            case_id=command.case_id,
            assignment_id=command.assignment_id,
            requirement_id=command.requirement_id,
            task_id=command.task_id,
        )
        version = session.scalar(
            sa.select(EnterpriseCapabilityVersionRecord).where(
                EnterpriseCapabilityVersionRecord.tenant_id == context.tenant_id,
                EnterpriseCapabilityVersionRecord.id == command.capability_version_id,
                EnterpriseCapabilityVersionRecord.capability_id == command.capability_id,
            )
        )
        capability = session.scalar(
            sa.select(EnterpriseCapabilityRecord).where(
                EnterpriseCapabilityRecord.tenant_id == context.tenant_id,
                EnterpriseCapabilityRecord.id == command.capability_id,
            )
        )
        if version is None or capability is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        validity_state = (
            "CURRENT"
            if capability.state == "ACTIVE"
            and version.valid_from <= context.received_at
            and (version.valid_until is None or version.valid_until > context.received_at)
            else "EXPIRED"
        )
        functional_key = ":".join(
            [
                str(command.case_id),
                str(command.capability_version_id),
                str(command.requirement_id or ""),
                str(command.task_id or ""),
            ]
        )
        existing = session.scalar(
            sa.select(CaseCapabilityProposalRecord).where(
                CaseCapabilityProposalRecord.tenant_id == context.tenant_id,
                CaseCapabilityProposalRecord.functional_key == functional_key,
            )
        )
        if existing is not None:
            raise CommandExecutionError("CAPABILITY_PROPOSAL_ALREADY_EXISTS")
        session.add(
            CaseCapabilityProposalRecord(
                id=command.proposal_id,
                tenant_id=context.tenant_id,
                case_id=command.case_id,
                assignment_id=command.assignment_id,
                capability_id=command.capability_id,
                capability_version_id=command.capability_version_id,
                requirement_id=command.requirement_id,
                task_id=command.task_id,
                state="PROPOSED",
                validity_state=validity_state,
                justification=command.justification,
                source_locator=command.source_locator,
                functional_key=functional_key,
                proposed_by_membership_id=context.membership_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )
        return HandlerOutcome(
            result_code="CAPABILITY_PROPOSED_FOR_CASE",
            aggregate_refs=(
                {
                    "aggregate_type": "CaseCapabilityProposal",
                    "aggregate_id": str(command.proposal_id),
                    "aggregate_revision": 0,
                    "validity_state": validity_state,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="CaseCapabilityProposal",
                    aggregate_id=command.proposal_id,
                    aggregate_revision=0,
                    event_type="CapabilityProposedForCase",
                    payload={
                        "proposal_id": str(command.proposal_id),
                        "case_id": str(command.case_id),
                        "capability_id": str(command.capability_id),
                        "capability_version_id": str(command.capability_version_id),
                        "validity_state": validity_state,
                    },
                ),
            ),
        )


class ReportCapabilityGapHandler:
    def execute(
        self,
        *,
        session: Session,
        command: ReportCapabilityGapCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        tenant_id = UUID(str(context.tenant_id))
        _require_active_assignment(
            session,
            context=context,
            case_id=command.case_id,
            assignment_id=command.assignment_id,
            required_action=Capability.PREPARATION_CAPABILITY_GAP_REPORT,
        )
        _validate_source(
            session,
            tenant_id=tenant_id,
            case_id=command.case_id,
            assignment_id=command.assignment_id,
            requirement_id=command.requirement_id,
            task_id=command.task_id,
        )
        if command.capability_id is not None:
            capability_exists = session.scalar(
                sa.select(EnterpriseCapabilityRecord.id).where(
                    EnterpriseCapabilityRecord.tenant_id == context.tenant_id,
                    EnterpriseCapabilityRecord.id == command.capability_id,
                )
            )
            if capability_exists is None:
                raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        functional_key = ":".join(
            [
                str(command.case_id),
                str(command.capability_id or ""),
                str(command.requirement_id or ""),
                str(command.task_id or ""),
                command.gap_kind,
            ]
        )
        existing = session.scalar(
            sa.select(CaseCapabilityGapRecord).where(
                CaseCapabilityGapRecord.tenant_id == context.tenant_id,
                CaseCapabilityGapRecord.functional_key == functional_key,
            )
        )
        if existing is not None:
            raise CommandExecutionError("CAPABILITY_GAP_ALREADY_REPORTED")
        session.add(
            CaseCapabilityGapRecord(
                id=command.gap_id,
                tenant_id=context.tenant_id,
                case_id=command.case_id,
                assignment_id=command.assignment_id,
                capability_id=command.capability_id,
                requirement_id=command.requirement_id,
                task_id=command.task_id,
                gap_kind=command.gap_kind,
                severity=command.severity,
                reason=command.reason,
                source_locator=command.source_locator,
                recommended_action=command.recommended_action,
                functional_key=functional_key,
                reported_by_membership_id=context.membership_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )
        return HandlerOutcome(
            result_code="CAPABILITY_GAP_REPORTED",
            aggregate_refs=(
                {
                    "aggregate_type": "CaseCapabilityGap",
                    "aggregate_id": str(command.gap_id),
                    "aggregate_revision": 0,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="CaseCapabilityGap",
                    aggregate_id=command.gap_id,
                    aggregate_revision=0,
                    event_type="CapabilityGapReported",
                    payload={
                        "gap_id": str(command.gap_id),
                        "case_id": str(command.case_id),
                        "capability_id": str(command.capability_id)
                        if command.capability_id
                        else None,
                        "gap_kind": command.gap_kind,
                        "severity": command.severity,
                    },
                ),
            ),
        )


def collaborator_capability_handlers() -> dict[str, CommandHandler]:
    return {
        "ProposeCapabilityForCase": ProposeCapabilityForCaseHandler(),
        "ReportCapabilityGap": ReportCapabilityGapHandler(),
    }

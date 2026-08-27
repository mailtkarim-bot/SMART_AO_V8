from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.enterprise.infrastructure.models import (
    CaseCapabilityGapRecord,
    CaseCapabilityProposalRecord,
)
from app.modules.membership.application.collab_capability_ports import (
    AssignmentProjection,
    CapabilityGapProjection,
    CapabilityProposalProjection,
    CollaboratorCapabilityAssessmentProjection,
    CollaboratorCapabilityReader,
)
from app.modules.membership.infrastructure.records import CaseAssignmentRecord
from app.platform.events.dispatcher import CommandExecutionError


class SqlAlchemyCollaboratorCapabilityReader(CollaboratorCapabilityReader):
    """SQLAlchemy adapter for collaborator capability authorization and reads."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def require_active_assignment(
        self,
        *,
        tenant_id: UUID,
        membership_id: UUID,
        case_id: UUID,
        assignment_id: UUID,
        required_action: str,
        received_at: datetime,
    ) -> AssignmentProjection:
        with self._session_factory() as session:
            assignment = session.scalar(
                sa.select(CaseAssignmentRecord).where(
                    CaseAssignmentRecord.tenant_id == tenant_id,
                    CaseAssignmentRecord.id == assignment_id,
                    CaseAssignmentRecord.case_id == case_id,
                    CaseAssignmentRecord.membership_id == membership_id,
                    CaseAssignmentRecord.state == "ACTIVE",
                    CaseAssignmentRecord.starts_at <= received_at,
                    sa.or_(
                        CaseAssignmentRecord.ends_at.is_(None),
                        CaseAssignmentRecord.ends_at > received_at,
                    ),
                )
            )
            if assignment is None:
                raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
            if required_action not in assignment.scope_actions_json:
                raise CommandExecutionError("SCOPE_DENIED")
            return AssignmentProjection(id=assignment.id, case_id=assignment.case_id)

    def read_assessments(
        self, *, tenant_id: UUID, case_id: UUID, assignment_id: UUID
    ) -> CollaboratorCapabilityAssessmentProjection:
        with self._session_factory() as session:
            proposals = tuple(
                CapabilityProposalProjection(
                    proposal_id=item.id,
                    case_id=item.case_id,
                    assignment_id=item.assignment_id,
                    capability_id=item.capability_id,
                    capability_version_id=item.capability_version_id,
                    requirement_id=item.requirement_id,
                    task_id=item.task_id,
                    state=item.state,
                    validity_state=item.validity_state,
                    justification=item.justification,
                    source_locator=item.source_locator,
                )
                for item in session.scalars(
                    sa.select(CaseCapabilityProposalRecord)
                    .where(
                        CaseCapabilityProposalRecord.tenant_id == tenant_id,
                        CaseCapabilityProposalRecord.case_id == case_id,
                        CaseCapabilityProposalRecord.assignment_id == assignment_id,
                    )
                    .order_by(
                        CaseCapabilityProposalRecord.created_at,
                        CaseCapabilityProposalRecord.id,
                    )
                ).all()
            )
            gaps = tuple(
                CapabilityGapProjection(
                    gap_id=item.id,
                    case_id=item.case_id,
                    assignment_id=item.assignment_id,
                    capability_id=item.capability_id,
                    requirement_id=item.requirement_id,
                    task_id=item.task_id,
                    gap_kind=item.gap_kind,
                    severity=item.severity,
                    reason=item.reason,
                    source_locator=item.source_locator,
                    recommended_action=item.recommended_action,
                )
                for item in session.scalars(
                    sa.select(CaseCapabilityGapRecord)
                    .where(
                        CaseCapabilityGapRecord.tenant_id == tenant_id,
                        CaseCapabilityGapRecord.case_id == case_id,
                        CaseCapabilityGapRecord.assignment_id == assignment_id,
                    )
                    .order_by(CaseCapabilityGapRecord.created_at, CaseCapabilityGapRecord.id)
                ).all()
            )
        return CollaboratorCapabilityAssessmentProjection(proposals=proposals, gaps=gaps)

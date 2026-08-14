"""SQLAlchemy reader for the closed collaborator Assignment history projection."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.membership.application.queries import (
    AssignmentHistoryItemProjection,
    AssignmentHistoryLookup,
)
from app.platform.security.models import (
    AssignmentClarificationRequestRecord,
    CaseAssignmentAcknowledgementRecord,
    CaseAssignmentRecord,
    CaseAssignmentUnavailabilityRecord,
)


class SqlAlchemyAssignmentHistoryReader:
    """Read one collaborator-owned assignment and its non-sensitive history facts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self,
        *,
        tenant_id: UUID,
        membership_id: UUID,
        assignment_id: UUID,
        limit: int,
    ) -> AssignmentHistoryLookup | None:
        assignment = self._session.execute(
            sa.select(
                CaseAssignmentRecord.id,
                CaseAssignmentRecord.case_id,
                CaseRecord.lifecycle,
            )
            .join(
                CaseRecord,
                sa.and_(
                    CaseRecord.tenant_id == CaseAssignmentRecord.tenant_id,
                    CaseRecord.id == CaseAssignmentRecord.case_id,
                ),
            )
            .where(
                CaseAssignmentRecord.tenant_id == tenant_id,
                CaseAssignmentRecord.membership_id == membership_id,
                CaseAssignmentRecord.id == assignment_id,
            )
        ).one_or_none()
        if assignment is None:
            return None

        items = (*self._acknowledgements(tenant_id, assignment_id, limit),)
        items += (*self._clarifications(tenant_id, assignment_id, limit),)
        items += (*self._unavailabilities(tenant_id, assignment_id, limit),)
        ordered = tuple(
            sorted(
                items,
                key=lambda item: (-item.recorded_at.timestamp(), str(item.record_id)),
            )[:limit]
        )
        return AssignmentHistoryLookup(
            assignment_id=assignment.id,
            case_id=assignment.case_id,
            case_lifecycle=assignment.lifecycle,
            items=ordered,
        )

    def _acknowledgements(
        self,
        tenant_id: UUID,
        assignment_id: UUID,
        limit: int,
    ) -> tuple[AssignmentHistoryItemProjection, ...]:
        rows = self._session.execute(
            sa.select(
                CaseAssignmentAcknowledgementRecord.id,
                CaseAssignmentAcknowledgementRecord.created_at,
                CaseAssignmentAcknowledgementRecord.assignment_revision,
            )
            .where(
                CaseAssignmentAcknowledgementRecord.tenant_id == tenant_id,
                CaseAssignmentAcknowledgementRecord.assignment_id == assignment_id,
            )
            .order_by(
                CaseAssignmentAcknowledgementRecord.created_at.desc(),
                CaseAssignmentAcknowledgementRecord.id.asc(),
            )
            .limit(limit)
        ).all()
        return tuple(
            AssignmentHistoryItemProjection(
                record_id=row.id,
                kind="ACKNOWLEDGEMENT",
                recorded_at=row.created_at,
                assignment_revision=row.assignment_revision,
                operational_state="RECORDED",
            )
            for row in rows
        )

    def _clarifications(
        self,
        tenant_id: UUID,
        assignment_id: UUID,
        limit: int,
    ) -> tuple[AssignmentHistoryItemProjection, ...]:
        rows = self._session.execute(
            sa.select(
                AssignmentClarificationRequestRecord.id,
                AssignmentClarificationRequestRecord.created_at,
                AssignmentClarificationRequestRecord.clarification_kind,
                AssignmentClarificationRequestRecord.priority,
                AssignmentClarificationRequestRecord.state,
            )
            .where(
                AssignmentClarificationRequestRecord.tenant_id == tenant_id,
                AssignmentClarificationRequestRecord.assignment_id == assignment_id,
            )
            .order_by(
                AssignmentClarificationRequestRecord.created_at.desc(),
                AssignmentClarificationRequestRecord.id.asc(),
            )
            .limit(limit)
        ).all()
        return tuple(
            AssignmentHistoryItemProjection(
                record_id=row.id,
                kind="CLARIFICATION_REQUEST",
                recorded_at=row.created_at,
                assignment_revision=None,
                operational_state=row.state,
                clarification_kind=row.clarification_kind,
                priority=row.priority,
            )
            for row in rows
        )

    def _unavailabilities(
        self,
        tenant_id: UUID,
        assignment_id: UUID,
        limit: int,
    ) -> tuple[AssignmentHistoryItemProjection, ...]:
        rows = self._session.execute(
            sa.select(
                CaseAssignmentUnavailabilityRecord.id,
                CaseAssignmentUnavailabilityRecord.created_at,
                CaseAssignmentUnavailabilityRecord.assignment_revision,
                CaseAssignmentUnavailabilityRecord.reason_kind,
                CaseAssignmentUnavailabilityRecord.unavailable_from,
                CaseAssignmentUnavailabilityRecord.unavailable_until,
                CaseAssignmentUnavailabilityRecord.known_deadline_impact,
            )
            .where(
                CaseAssignmentUnavailabilityRecord.tenant_id == tenant_id,
                CaseAssignmentUnavailabilityRecord.assignment_id == assignment_id,
            )
            .order_by(
                CaseAssignmentUnavailabilityRecord.created_at.desc(),
                CaseAssignmentUnavailabilityRecord.id.asc(),
            )
            .limit(limit)
        ).all()
        return tuple(
            AssignmentHistoryItemProjection(
                record_id=row.id,
                kind="UNAVAILABILITY_REPORT",
                recorded_at=row.created_at,
                assignment_revision=row.assignment_revision,
                operational_state="RECORDED",
                reason_kind=row.reason_kind,
                unavailable_from=row.unavailable_from,
                unavailable_until=row.unavailable_until,
                known_deadline_impact=row.known_deadline_impact,
            )
            for row in rows
        )

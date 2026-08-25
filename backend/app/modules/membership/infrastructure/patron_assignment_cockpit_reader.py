"""Tenant-scoped SQLAlchemy reader for the patron assignment authority cockpit."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.membership.application.queries import (
    AssignmentHistoryItemProjection,
    PatronAssignmentCockpitItemProjection,
    PatronAssignmentInteractionsLookup,
    PatronAssignmentJournalItemProjection,
    PatronAssignmentJournalLookup,
)
from app.modules.membership.infrastructure.records import (
    AssignmentClarificationRequestRecord,
    CaseAssignmentAcknowledgementRecord,
    CaseAssignmentChangeEventRecord,
    CaseAssignmentRecord,
    CaseAssignmentUnavailabilityRecord,
)


class SqlAlchemyPatronAssignmentCockpitReader:
    """Select explicit, closed patron projections from assignment authority records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID | None,
        state: str | None,
        limit: int,
    ) -> tuple[PatronAssignmentCockpitItemProjection, ...]:
        statement = self._assignment_header_statement(tenant_id=tenant_id)
        if case_id is not None:
            statement = statement.where(CaseAssignmentRecord.case_id == case_id)
        if state is not None:
            statement = statement.where(CaseAssignmentRecord.state == state)
        rows = self._session.execute(
            statement.order_by(CaseRecord.title.asc(), CaseAssignmentRecord.id.asc()).limit(limit)
        ).all()
        return tuple(self._to_assignment_projection(row) for row in rows)

    def get_journal(
        self,
        *,
        tenant_id: UUID,
        assignment_id: UUID,
        limit: int,
    ) -> PatronAssignmentJournalLookup | None:
        assignment_row = self._session.execute(
            self._assignment_header_statement(tenant_id=tenant_id).where(
                CaseAssignmentRecord.id == assignment_id
            )
        ).one_or_none()
        if assignment_row is None:
            return None
        rows = self._session.execute(
            sa.select(
                CaseAssignmentChangeEventRecord.id,
                CaseAssignmentChangeEventRecord.created_at,
                CaseAssignmentChangeEventRecord.event_type,
                CaseAssignmentChangeEventRecord.previous_revision,
                CaseAssignmentChangeEventRecord.resulting_revision,
                CaseAssignmentChangeEventRecord.previous_state,
                CaseAssignmentChangeEventRecord.resulting_state,
                CaseAssignmentChangeEventRecord.reason_code,
                CaseAssignmentChangeEventRecord.previous_scope_actions_json,
                CaseAssignmentChangeEventRecord.previous_scope_classifications_json,
                CaseAssignmentChangeEventRecord.resulting_scope_actions_json,
                CaseAssignmentChangeEventRecord.resulting_scope_classifications_json,
            )
            .where(
                CaseAssignmentChangeEventRecord.tenant_id == tenant_id,
                CaseAssignmentChangeEventRecord.assignment_id == assignment_id,
            )
            .order_by(
                CaseAssignmentChangeEventRecord.created_at.desc(),
                CaseAssignmentChangeEventRecord.id.asc(),
            )
            .limit(limit)
        ).all()
        return PatronAssignmentJournalLookup(
            assignment=self._to_assignment_projection(assignment_row),
            items=tuple(
                PatronAssignmentJournalItemProjection(
                    record_id=row.id,
                    recorded_at=row.created_at,
                    event_type=row.event_type,
                    previous_revision=row.previous_revision,
                    resulting_revision=row.resulting_revision,
                    previous_state=row.previous_state,
                    resulting_state=row.resulting_state,
                    reason_code=row.reason_code,
                    previous_scope_actions=(
                        tuple(row.previous_scope_actions_json)
                        if row.previous_scope_actions_json is not None
                        else None
                    ),
                    previous_scope_classifications=(
                        tuple(row.previous_scope_classifications_json)
                        if row.previous_scope_classifications_json is not None
                        else None
                    ),
                    resulting_scope_actions=tuple(row.resulting_scope_actions_json),
                    resulting_scope_classifications=tuple(row.resulting_scope_classifications_json),
                )
                for row in rows
            ),
        )

    def get_interactions(
        self,
        *,
        tenant_id: UUID,
        assignment_id: UUID,
        kind: str | None,
        limit: int,
    ) -> PatronAssignmentInteractionsLookup | None:
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
                CaseAssignmentRecord.id == assignment_id,
            )
        ).one_or_none()
        if assignment is None:
            return None
        interactions = sa.union_all(
            self._acknowledgements_statement(tenant_id=tenant_id, assignment_id=assignment_id),
            self._clarifications_statement(tenant_id=tenant_id, assignment_id=assignment_id),
            self._unavailabilities_statement(tenant_id=tenant_id, assignment_id=assignment_id),
        ).subquery()
        statement = sa.select(interactions)
        if kind is not None:
            statement = statement.where(interactions.c.kind == kind)
        rows = self._session.execute(
            statement.order_by(
                interactions.c.recorded_at.desc(),
                interactions.c.record_id.asc(),
            ).limit(limit)
        ).all()
        return PatronAssignmentInteractionsLookup(
            assignment_id=assignment.id,
            case_id=assignment.case_id,
            case_lifecycle=assignment.lifecycle,
            items=tuple(
                AssignmentHistoryItemProjection(
                    record_id=row.record_id,
                    kind=row.kind,
                    recorded_at=row.recorded_at,
                    assignment_revision=row.assignment_revision,
                    operational_state=row.operational_state,
                    clarification_kind=row.clarification_kind,
                    priority=row.priority,
                    reason_kind=row.reason_kind,
                    unavailable_from=row.unavailable_from,
                    unavailable_until=row.unavailable_until,
                    known_deadline_impact=row.known_deadline_impact,
                )
                for row in rows
            ),
        )

    @staticmethod
    def _acknowledgements_statement(*, tenant_id: UUID, assignment_id: UUID):
        return sa.select(
            CaseAssignmentAcknowledgementRecord.id.label("record_id"),
            CaseAssignmentAcknowledgementRecord.created_at.label("recorded_at"),
            sa.literal("ACKNOWLEDGEMENT").label("kind"),
            CaseAssignmentAcknowledgementRecord.assignment_revision,
            sa.literal("RECORDED").label("operational_state"),
            sa.cast(sa.null(), sa.String()).label("clarification_kind"),
            sa.cast(sa.null(), sa.String()).label("priority"),
            sa.cast(sa.null(), sa.String()).label("reason_kind"),
            sa.cast(sa.null(), sa.DateTime(timezone=True)).label("unavailable_from"),
            sa.cast(sa.null(), sa.DateTime(timezone=True)).label("unavailable_until"),
            sa.cast(sa.null(), sa.Boolean()).label("known_deadline_impact"),
        ).where(
            CaseAssignmentAcknowledgementRecord.tenant_id == tenant_id,
            CaseAssignmentAcknowledgementRecord.assignment_id == assignment_id,
        )

    @staticmethod
    def _clarifications_statement(*, tenant_id: UUID, assignment_id: UUID):
        return sa.select(
            AssignmentClarificationRequestRecord.id.label("record_id"),
            AssignmentClarificationRequestRecord.created_at.label("recorded_at"),
            sa.literal("CLARIFICATION_REQUEST").label("kind"),
            sa.cast(sa.null(), sa.Integer()).label("assignment_revision"),
            AssignmentClarificationRequestRecord.state.label("operational_state"),
            AssignmentClarificationRequestRecord.clarification_kind,
            AssignmentClarificationRequestRecord.priority,
            sa.cast(sa.null(), sa.String()).label("reason_kind"),
            sa.cast(sa.null(), sa.DateTime(timezone=True)).label("unavailable_from"),
            sa.cast(sa.null(), sa.DateTime(timezone=True)).label("unavailable_until"),
            sa.cast(sa.null(), sa.Boolean()).label("known_deadline_impact"),
        ).where(
            AssignmentClarificationRequestRecord.tenant_id == tenant_id,
            AssignmentClarificationRequestRecord.assignment_id == assignment_id,
        )

    @staticmethod
    def _unavailabilities_statement(*, tenant_id: UUID, assignment_id: UUID):
        return sa.select(
            CaseAssignmentUnavailabilityRecord.id.label("record_id"),
            CaseAssignmentUnavailabilityRecord.created_at.label("recorded_at"),
            sa.literal("UNAVAILABILITY_REPORT").label("kind"),
            CaseAssignmentUnavailabilityRecord.assignment_revision,
            sa.literal("RECORDED").label("operational_state"),
            sa.cast(sa.null(), sa.String()).label("clarification_kind"),
            sa.cast(sa.null(), sa.String()).label("priority"),
            CaseAssignmentUnavailabilityRecord.reason_kind,
            CaseAssignmentUnavailabilityRecord.unavailable_from,
            CaseAssignmentUnavailabilityRecord.unavailable_until,
            CaseAssignmentUnavailabilityRecord.known_deadline_impact,
        ).where(
            CaseAssignmentUnavailabilityRecord.tenant_id == tenant_id,
            CaseAssignmentUnavailabilityRecord.assignment_id == assignment_id,
        )

    @staticmethod
    def _assignment_header_statement(*, tenant_id: UUID):
        return (
            sa.select(
                CaseAssignmentRecord.id.label("assignment_id"),
                CaseAssignmentRecord.case_id,
                CaseRecord.title.label("case_title"),
                CaseRecord.lifecycle.label("case_lifecycle"),
                CaseAssignmentRecord.state,
                CaseAssignmentRecord.aggregate_revision,
                CaseAssignmentRecord.starts_at,
                CaseAssignmentRecord.ends_at,
                CaseAssignmentRecord.ended_at,
                CaseAssignmentRecord.scope_actions_json,
                CaseAssignmentRecord.scope_classifications_json,
            )
            .join(
                CaseRecord,
                sa.and_(
                    CaseRecord.tenant_id == CaseAssignmentRecord.tenant_id,
                    CaseRecord.id == CaseAssignmentRecord.case_id,
                ),
            )
            .where(CaseAssignmentRecord.tenant_id == tenant_id)
        )

    @staticmethod
    def _to_assignment_projection(row) -> PatronAssignmentCockpitItemProjection:
        return PatronAssignmentCockpitItemProjection(
            assignment_id=row.assignment_id,
            case_id=row.case_id,
            case_title=row.case_title,
            case_lifecycle=row.case_lifecycle,
            state=row.state,
            aggregate_revision=row.aggregate_revision,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            ended_at=row.ended_at,
            scope_actions=tuple(row.scope_actions_json),
            scope_classifications=tuple(row.scope_classifications_json),
        )

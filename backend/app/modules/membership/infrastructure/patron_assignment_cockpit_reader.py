"""Tenant-scoped SQLAlchemy reader for the patron assignment authority cockpit."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.membership.application.queries import (
    PatronAssignmentCockpitItemProjection,
    PatronAssignmentJournalItemProjection,
    PatronAssignmentJournalLookup,
)
from app.platform.security.models import CaseAssignmentChangeEventRecord, CaseAssignmentRecord


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

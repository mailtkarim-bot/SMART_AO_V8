from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.membership.application.queries import (
    AssignmentManagementCase,
    AssignmentManagementTarget,
)
from app.modules.membership.infrastructure.records import CaseAssignmentRecord


class SqlAlchemyAssignmentManagementReader:
    """SQLAlchemy adapter for tenant-scoped assignment management lookups."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def get_case(self, *, tenant_id: UUID, case_id: UUID) -> AssignmentManagementCase | None:
        with self._session_factory() as session:
            record = session.scalar(
                sa.select(CaseRecord).where(
                    CaseRecord.tenant_id == tenant_id,
                    CaseRecord.id == case_id,
                )
            )
        if record is None:
            return None
        return AssignmentManagementCase(id=record.id, lifecycle=record.lifecycle)

    def get_assignment(
        self, *, tenant_id: UUID, assignment_id: UUID
    ) -> AssignmentManagementTarget | None:
        with self._session_factory() as session:
            record = session.scalar(
                sa.select(CaseAssignmentRecord).where(
                    CaseAssignmentRecord.tenant_id == tenant_id,
                    CaseAssignmentRecord.id == assignment_id,
                )
            )
        if record is None:
            return None
        return AssignmentManagementTarget(id=record.id, case_id=record.case_id)

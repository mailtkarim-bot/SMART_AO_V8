"""Closed Case collection reader for the authenticated collaborator workspace."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.queries import AssignedCaseProjection


class SqlAlchemyAssignedCaseReader:
    """Read Case candidates by tenant; SEC-01 filters them before serialization."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, *, tenant_id: UUID | str) -> tuple[AssignedCaseProjection, ...]:
        statement = (
            sa.select(
                CaseRecord.id,
                CaseRecord.title,
                CaseRecord.lifecycle,
                CaseRecord.commercial_stage,
                CaseRecord.dce_freshness,
            )
            .where(
                CaseRecord.tenant_id == tenant_id,
                CaseRecord.lifecycle != "ARCHIVED",
            )
            .order_by(CaseRecord.updated_at.desc(), CaseRecord.id.asc())
        )
        rows = self._session.execute(statement).all()
        return tuple(
            AssignedCaseProjection(
                case_id=row.id,
                work_label=row.title,
                case_lifecycle=row.lifecycle,
                commercial_stage=row.commercial_stage,
                dce_availability=row.dce_freshness,
            )
            for row in rows
        )

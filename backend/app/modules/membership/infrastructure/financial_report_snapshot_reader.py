from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.pricing.infrastructure.models import FinancialReportSnapshotRecord


class SqlAlchemyFinancialReportSnapshotReader:
    """Infrastructure adapter for tenant-scoped financial snapshot existence."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def exists(self, *, tenant_id: UUID, case_id: UUID, report_id: UUID) -> bool:
        with self._session_factory() as session:
            snapshot_id = session.scalar(
                sa.select(FinancialReportSnapshotRecord.id).where(
                    FinancialReportSnapshotRecord.tenant_id == tenant_id,
                    FinancialReportSnapshotRecord.case_id == case_id,
                    FinancialReportSnapshotRecord.id == report_id,
                )
            )
        return snapshot_id is not None

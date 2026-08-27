from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.case.infrastructure.models.case import CaseRecord


class SqlAlchemyFinancialDraftCaseReader:
    """Infrastructure adapter for tenant-scoped Case existence checks."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def exists(self, *, tenant_id: UUID, case_id: UUID) -> bool:
        with self._session_factory() as session:
            case_id_value = session.scalar(
                sa.select(CaseRecord.id).where(
                    CaseRecord.tenant_id == tenant_id,
                    CaseRecord.id == case_id,
                )
            )
        return case_id_value is not None

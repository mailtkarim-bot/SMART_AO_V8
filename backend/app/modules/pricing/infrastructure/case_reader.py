from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.case.infrastructure.models.case import CaseRecord


class SqlAlchemyCaseExistenceReader:
    """Infrastructure adapter for the pricing application CaseExistenceReader port."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def exists(self, *, tenant_id: UUID, case_id: UUID) -> bool:
        with self._session_factory() as session:
            return session.scalar(
                sa.select(CaseRecord.id).where(
                    CaseRecord.tenant_id == tenant_id,
                    CaseRecord.id == case_id,
                )
            ) is not None

from uuid import UUID

import sqlalchemy as sa
from app.modules.enterprise.infrastructure.models import EnterpriseCapabilityRecord
from sqlalchemy.orm import Session, sessionmaker


class SqlAlchemyEnterpriseCapabilityContextReader:
    """Infrastructure adapter for tenant-scoped capability ownership lookup."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def company_id_for_capability(
        self, *, tenant_id: UUID, capability_id: UUID
    ) -> UUID | None:
        with self._session_factory() as session:
            return session.scalar(
                sa.select(EnterpriseCapabilityRecord.company_id).where(
                    EnterpriseCapabilityRecord.tenant_id == tenant_id,
                    EnterpriseCapabilityRecord.id == capability_id,
                )
            )

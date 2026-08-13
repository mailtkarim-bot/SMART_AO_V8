"""SQLAlchemy read adapter for the minimal Consultation RYOW projection."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.dce.application.queries import (
    ConsultationProjection,
    ConsultationProjectionReader,
)
from app.modules.dce.infrastructure.models.consultation import (
    ConsultationLotRecord,
    ConsultationRecord,
    ConsultationTrancheRecord,
)


class SqlAlchemyConsultationProjectionReader(ConsultationProjectionReader):
    """Rebuilds one tenant-filtered consultation view from its owned records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self,
        *,
        tenant_id: UUID | str,
        consultation_id: UUID | str,
    ) -> ConsultationProjection | None:
        root = self._session.scalar(
            sa.select(ConsultationRecord).where(
                ConsultationRecord.tenant_id == tenant_id,
                ConsultationRecord.id == consultation_id,
            )
        )
        if root is None:
            return None

        lots = tuple(
            record.lot_number
            for record in self._session.scalars(
                sa.select(ConsultationLotRecord)
                .where(
                    ConsultationLotRecord.tenant_id == tenant_id,
                    ConsultationLotRecord.consultation_id == consultation_id,
                )
                .order_by(ConsultationLotRecord.lot_number, ConsultationLotRecord.id)
            )
        )
        tranches = tuple(
            record.tranche_reference
            for record in self._session.scalars(
                sa.select(ConsultationTrancheRecord)
                .where(
                    ConsultationTrancheRecord.tenant_id == tenant_id,
                    ConsultationTrancheRecord.consultation_id == consultation_id,
                )
                .order_by(ConsultationTrancheRecord.tranche_reference, ConsultationTrancheRecord.id)
            )
        )
        return ConsultationProjection(
            id=root.id,
            buyer_legal_name=root.buyer_legal_name,
            external_reference=root.external_reference,
            object_label=root.object_label,
            location_label=root.location_label,
            lifecycle=root.lifecycle,
            freshness=root.freshness,
            aggregate_revision=root.aggregate_revision,
            lots=lots,
            tranches=tranches,
        )

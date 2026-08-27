from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.pricing.application.import_read import (
    PricingImportBatchProjection,
    PricingImportRowProjection,
)
from app.modules.pricing.infrastructure.models import (
    PricingImportBatchRecord,
    PricingImportRowRecord,
    PricingImportTransitionRecord,
)


class SqlAlchemyImportPreviewReader:
    """Infrastructure adapter for normalized pricing previews and current state."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get(
        self, *, tenant_id: UUID, case_id: UUID, batch_id: UUID
    ) -> PricingImportBatchProjection | None:
        with self._session_factory() as session:
            batch = session.scalar(
                sa.select(PricingImportBatchRecord).where(
                    PricingImportBatchRecord.tenant_id == tenant_id,
                    PricingImportBatchRecord.case_id == case_id,
                    PricingImportBatchRecord.id == batch_id,
                )
            )
            if batch is None:
                return None
            latest_transition = session.scalar(
                sa.select(PricingImportTransitionRecord)
                .where(
                    PricingImportTransitionRecord.tenant_id == tenant_id,
                    PricingImportTransitionRecord.batch_id == batch.id,
                )
                .order_by(PricingImportTransitionRecord.version.desc())
                .limit(1)
            )
            current_state = latest_transition.to_state if latest_transition else batch.state
            current_revision = (
                latest_transition.version
                if latest_transition
                else batch.aggregate_revision
            )
            rows = session.scalars(
                sa.select(PricingImportRowRecord)
                .where(
                    PricingImportRowRecord.tenant_id == tenant_id,
                    PricingImportRowRecord.batch_id == batch.id,
                )
                .order_by(PricingImportRowRecord.row_number)
            ).all()
        return PricingImportBatchProjection(
            batch_id=batch.id,
            case_id=batch.case_id,
            document_kind=batch.document_kind,
            state=current_state,
            aggregate_revision=current_revision,
            row_count=batch.row_count,
            valid_row_count=batch.valid_row_count,
            error_count=batch.error_count,
            total_minor=batch.total_minor,
            rows=tuple(
                PricingImportRowProjection(
                    row_number=row.row_number,
                    code=row.code,
                    designation=row.designation,
                    unit=row.unit,
                    quantity_decimal=row.quantity_decimal,
                    unit_price_minor=row.unit_price_minor,
                    total_minor=row.total_minor,
                    errors=tuple(row.error_codes_json or []),
                )
                for row in rows
            ),
        )

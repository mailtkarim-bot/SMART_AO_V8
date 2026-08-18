"""SQLAlchemy adapter for the preparation DCE read port."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.dce.infrastructure.models.dce_requirement_confirmations import (
    DceRequirementConfirmationCurrentRecord,
)
from app.modules.dce.infrastructure.models.dce_requirements import DceRequirementRecord
from app.modules.dce.infrastructure.models.dce_version import DceVersionRecord
from app.modules.preparation.application.ports import (
    PreparationDceInput,
    PreparationRequirementInput,
)


class SqlAlchemyPreparationDceReader:
    """Translate DCE ORM records into the preparation read contract."""

    def read(
        self,
        *,
        session: Session,
        tenant_id: UUID,
        dce_version_id: UUID,
        as_of: datetime,
    ) -> PreparationDceInput | None:
        del as_of
        dce = session.scalar(
            sa.select(DceVersionRecord).where(
                DceVersionRecord.tenant_id == tenant_id,
                DceVersionRecord.id == dce_version_id,
            )
        )
        if dce is None:
            return None
        requirements = tuple(
            PreparationRequirementInput(
                requirement_id=requirement.id,
                requirement_type=requirement.requirement_type,
                directive_signal=requirement.directive_signal,
                confirmation_outcome=(
                    confirmation.outcome
                    if (
                        confirmation := session.scalar(
                            sa.select(DceRequirementConfirmationCurrentRecord).where(
                                DceRequirementConfirmationCurrentRecord.tenant_id == tenant_id,
                                DceRequirementConfirmationCurrentRecord.requirement_id
                                == requirement.id,
                            )
                        )
                    )
                    is not None
                    else None
                ),
            )
            for requirement in session.scalars(
                sa.select(DceRequirementRecord)
                .where(
                    DceRequirementRecord.tenant_id == tenant_id,
                    DceRequirementRecord.dce_version_id == dce_version_id,
                )
                .order_by(DceRequirementRecord.id)
            ).all()
        )
        return PreparationDceInput(
            analysis_readiness=dce.analysis_readiness,
            requirements=requirements,
        )

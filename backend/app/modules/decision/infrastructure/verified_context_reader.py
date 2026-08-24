from __future__ import annotations

from typing import cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.infrastructure.models.dce_requirement_confirmations import (
    DceRequirementConfirmationCurrentRecord,
)
from app.modules.dce.infrastructure.models.dce_requirements import DceRequirementRecord
from app.modules.decision.application.ports import DecisionVerifiedContextReader
from app.modules.decision.infrastructure.models.decision import DecisionContextReferenceRecord


class SqlAlchemyDecisionVerifiedContextReader(DecisionVerifiedContextReader):
    """Check Decision context DCE references against current human confirmations."""

    def has_confirmed_dce_requirements(
        self, *, session: object, tenant_id: UUID, context_id: UUID, case_id: UUID
    ) -> bool:
        db_session = cast(Session, session)
        applicable_dce_version_id = db_session.scalar(
            sa.select(CaseRecord.applicable_dce_version_id).where(
                CaseRecord.tenant_id == tenant_id,
                CaseRecord.id == case_id,
            )
        )
        if applicable_dce_version_id is None:
            return False
        requirement_ids = list(
            db_session.scalars(
                sa.select(DecisionContextReferenceRecord.aggregate_id).where(
                    DecisionContextReferenceRecord.tenant_id == tenant_id,
                    DecisionContextReferenceRecord.decision_context_id == context_id,
                    DecisionContextReferenceRecord.aggregate_type == "DCE_REQUIREMENT",
                )
            )
        )
        if not requirement_ids:
            return True
        confirmed_count = db_session.scalar(
            sa.select(sa.func.count(DceRequirementRecord.id))
            .join(
                DceRequirementConfirmationCurrentRecord,
                sa.and_(
                    DceRequirementConfirmationCurrentRecord.tenant_id
                    == DceRequirementRecord.tenant_id,
                    DceRequirementConfirmationCurrentRecord.requirement_id
                    == DceRequirementRecord.id,
                ),
            )
            .where(
                DceRequirementRecord.tenant_id == tenant_id,
                DceRequirementRecord.dce_version_id == applicable_dce_version_id,
                DceRequirementRecord.id.in_(requirement_ids),
                DceRequirementConfirmationCurrentRecord.outcome == "CONFIRMED",
            )
        )
        return int(confirmed_count or 0) == len(requirement_ids)

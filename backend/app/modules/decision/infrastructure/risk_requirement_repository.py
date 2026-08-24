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
from app.modules.decision.application.ports import DecisionRiskRequirementLinkDraft
from app.modules.decision.infrastructure.models.risk import DecisionRiskRecord
from app.modules.decision.infrastructure.models.risk_requirement import (
    DecisionRiskRequirementLinkRecord,
)


class SqlAlchemyDecisionRiskRequirementLinkRepository:
    """SQLAlchemy adapter for confirmed, tenant-scoped risk–requirement links."""

    def case_exists(self, *, session: object, tenant_id: UUID, case_id: UUID) -> bool:
        db_session = cast(Session, session)
        return (
            db_session.scalar(
                sa.select(CaseRecord.id).where(
                    CaseRecord.tenant_id == tenant_id,
                    CaseRecord.id == case_id,
                )
            )
            is not None
        )

    def case_uses_dce_version(
        self, *, session: object, tenant_id: UUID, case_id: UUID, dce_version_id: UUID
    ) -> bool:
        db_session = cast(Session, session)
        return (
            db_session.scalar(
                sa.select(CaseRecord.id).where(
                    CaseRecord.tenant_id == tenant_id,
                    CaseRecord.id == case_id,
                    CaseRecord.applicable_dce_version_id == dce_version_id,
                )
            )
            is not None
        )

    def risk_matches_case_and_version(
        self,
        *,
        session: object,
        tenant_id: UUID,
        risk_id: UUID,
        case_id: UUID,
        dce_version_id: UUID,
    ) -> bool:
        db_session = cast(Session, session)
        return (
            db_session.scalar(
                sa.select(DecisionRiskRecord.id).where(
                    DecisionRiskRecord.tenant_id == tenant_id,
                    DecisionRiskRecord.id == risk_id,
                    DecisionRiskRecord.case_id == case_id,
                    DecisionRiskRecord.dce_version_id == dce_version_id,
                )
            )
            is not None
        )

    def requirement_is_confirmed(
        self, *, session: object, tenant_id: UUID, requirement_id: UUID, dce_version_id: UUID
    ) -> bool:
        db_session = cast(Session, session)
        return (
            db_session.scalar(
                sa.select(DceRequirementRecord.id)
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
                    DceRequirementRecord.id == requirement_id,
                    DceRequirementRecord.dce_version_id == dce_version_id,
                    DceRequirementConfirmationCurrentRecord.outcome == "CONFIRMED",
                )
            )
            is not None
        )

    def functional_exists(
        self, *, session: object, tenant_id: UUID, functional_key: str
    ) -> bool:
        db_session = cast(Session, session)
        return (
            db_session.scalar(
                sa.select(DecisionRiskRequirementLinkRecord.id).where(
                    DecisionRiskRequirementLinkRecord.tenant_id == tenant_id,
                    DecisionRiskRequirementLinkRecord.functional_key == functional_key,
                )
            )
            is not None
        )

    def create(self, *, session: object, draft: DecisionRiskRequirementLinkDraft) -> None:
        db_session = cast(Session, session)
        draft.link.validate()
        db_session.add(
            DecisionRiskRequirementLinkRecord(
                id=draft.id,
                tenant_id=draft.tenant_id,
                case_id=draft.case_id,
                risk_id=draft.risk_id,
                requirement_id=draft.requirement_id,
                dce_version_id=draft.dce_version_id,
                functional_key=draft.functional_key,
                relationship=draft.link.relationship.value,
                rationale=draft.link.rationale,
                source_refs_json=[
                    f"decision-risk:{draft.risk_id}",
                    f"dce-requirement:{draft.requirement_id}",
                ],
                actor_id=draft.actor_id,
                membership_id=draft.membership_id,
                command_id=draft.command_id,
                idempotency_key=draft.idempotency_key,
                correlation_id=draft.correlation_id,
            )
        )

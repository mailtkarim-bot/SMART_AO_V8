from __future__ import annotations

from typing import cast
from uuid import UUID

import sqlalchemy as sa
from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.infrastructure.models.dce_requirement_confirmations import (
    DceRequirementConfirmationCurrentRecord,
)
from app.modules.dce.infrastructure.models.dce_requirements import DceRequirementRecord
from app.modules.decision.domain.submission_gate import DecisionSubmissionGateSnapshot
from app.modules.decision.infrastructure.models.decision import (
    DecisionConditionRecord,
    DecisionContextReferenceRecord,
    DecisionRecord,
)
from app.modules.decision.infrastructure.models.risk_requirement import (
    DecisionRiskRequirementLinkRecord,
)
from app.modules.patron_action.infrastructure.models import (
    PatronActionRecord,
    PatronActionTransitionRecord,
)
from app.modules.submission.application.ports import SubmissionDecisionGateReader
from sqlalchemy.orm import Session


class SqlAlchemySubmissionDecisionGateReader(SubmissionDecisionGateReader):
    """Read only the tenant-scoped, non-financial facts needed by Submission."""

    def read(
        self, *, session: object, tenant_id: UUID, case_id: UUID
    ) -> DecisionSubmissionGateSnapshot | None:
        db_session = cast(Session, session)
        decision = db_session.scalar(
            sa.select(DecisionRecord)
            .where(
                DecisionRecord.tenant_id == tenant_id,
                DecisionRecord.case_id == case_id,
                DecisionRecord.decision_type == "GO_NO_GO",
                DecisionRecord.validity == "CURRENT",
            )
            .order_by(DecisionRecord.cycle_number.desc(), DecisionRecord.updated_at.desc())
            .limit(1)
        )
        if decision is None:
            return None

        context_id = decision.selected_final_context_id
        all_dce_requirements_confirmed = self._all_dce_requirements_confirmed(
            session=db_session,
            tenant_id=tenant_id,
            case_id=case_id,
            context_id=context_id,
        )
        open_condition_count = int(
            db_session.scalar(
                sa.select(sa.func.count(DecisionConditionRecord.id)).where(
                    DecisionConditionRecord.tenant_id == tenant_id,
                    DecisionConditionRecord.decision_id == decision.id,
                    DecisionConditionRecord.status == "OPEN",
                )
            )
            or 0
        )
        unresolved_risk_action_count = self._unresolved_risk_action_count(
            session=db_session,
            tenant_id=tenant_id,
            case_id=case_id,
        )
        return DecisionSubmissionGateSnapshot(
            lifecycle=decision.lifecycle,
            outcome=decision.outcome,
            context_status=decision.context_status,
            condition_status=decision.condition_status,
            open_condition_count=open_condition_count,
            unresolved_risk_action_count=unresolved_risk_action_count,
            all_dce_requirements_confirmed=all_dce_requirements_confirmed,
        )

    @staticmethod
    def _all_dce_requirements_confirmed(
        *, session: Session, tenant_id: UUID, case_id: UUID, context_id: UUID | None
    ) -> bool:
        if context_id is None:
            return False
        applicable_dce_version_id = session.scalar(
            sa.select(CaseRecord.applicable_dce_version_id).where(
                CaseRecord.tenant_id == tenant_id,
                CaseRecord.id == case_id,
            )
        )
        if applicable_dce_version_id is None:
            return False
        requirement_ids = list(
            session.scalars(
                sa.select(DecisionContextReferenceRecord.aggregate_id).where(
                    DecisionContextReferenceRecord.tenant_id == tenant_id,
                    DecisionContextReferenceRecord.decision_context_id == context_id,
                    DecisionContextReferenceRecord.aggregate_type == "DCE_REQUIREMENT",
                )
            )
        )
        if not requirement_ids:
            return True
        confirmed_count = session.scalar(
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

    @staticmethod
    def _unresolved_risk_action_count(
        *, session: Session, tenant_id: UUID, case_id: UUID
    ) -> int:
        action_key = sa.func.concat(
            "decision-risk-requirement:", DecisionRiskRequirementLinkRecord.id
        )
        rows = session.execute(
            sa.select(
                DecisionRiskRequirementLinkRecord.id,
                PatronActionRecord.id,
                PatronActionRecord.state,
            )
            .outerjoin(
                PatronActionRecord,
                sa.and_(
                    PatronActionRecord.tenant_id == tenant_id,
                    PatronActionRecord.case_id == case_id,
                    PatronActionRecord.functional_key == action_key,
                ),
            )
            .where(
                DecisionRiskRequirementLinkRecord.tenant_id == tenant_id,
                DecisionRiskRequirementLinkRecord.case_id == case_id,
            )
        ).all()
        unresolved = 0
        for _link_id, action_id, base_state in rows:
            if action_id is None:
                unresolved += 1
                continue
            latest_state = session.scalar(
                sa.select(PatronActionTransitionRecord.to_state)
                .where(
                    PatronActionTransitionRecord.tenant_id == tenant_id,
                    PatronActionTransitionRecord.action_id == action_id,
                )
                .order_by(PatronActionTransitionRecord.aggregate_revision.desc())
                .limit(1)
            )
            if (latest_state or base_state) not in {"COMPLETED", "ABANDONED"}:
                unresolved += 1
        return unresolved

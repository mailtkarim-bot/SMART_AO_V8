from __future__ import annotations

import base64
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.decision.application.queries import (
    DecisionPricingReconciliationProjection,
    DecisionRiskRequirementLinkProjection,
    DecisionRiskRequirementPage,
)
from app.modules.decision.infrastructure.models.risk_requirement import (
    DecisionRiskRequirementLinkRecord,
)
from app.modules.patron_action.infrastructure.models import (
    PatronActionRecord,
    PatronActionTransitionRecord,
)
from app.modules.pricing.infrastructure.models.financial import (
    PricingImportBatchRecord,
    PricingImportRowRecord,
)


class SqlAlchemyDecisionRiskRequirementReader:
    """Read patron-only links and controlled pricing candidates with tenant filters."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_for_case(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        limit: int,
        after_created_at: datetime | None,
        after_id: UUID | None,
    ) -> DecisionRiskRequirementPage:
        latest_state = (
            sa.select(PatronActionTransitionRecord.to_state)
            .where(
                PatronActionTransitionRecord.tenant_id == tenant_id,
                PatronActionTransitionRecord.action_id == PatronActionRecord.id,
            )
            .order_by(PatronActionTransitionRecord.aggregate_revision.desc())
            .limit(1)
            .scalar_subquery()
        )
        latest_revision = (
            sa.select(PatronActionTransitionRecord.aggregate_revision)
            .where(
                PatronActionTransitionRecord.tenant_id == tenant_id,
                PatronActionTransitionRecord.action_id == PatronActionRecord.id,
            )
            .order_by(PatronActionTransitionRecord.aggregate_revision.desc())
            .limit(1)
            .scalar_subquery()
        )
        action_key = sa.func.concat(
            "decision-risk-requirement:", DecisionRiskRequirementLinkRecord.id
        )
        page_limit = min(max(limit, 1), 100)
        statement = (
            sa.select(
                DecisionRiskRequirementLinkRecord,
                PatronActionRecord,
                latest_state,
                latest_revision,
            )
            .outerjoin(
                PatronActionRecord,
                sa.and_(
                    PatronActionRecord.tenant_id == tenant_id,
                    PatronActionRecord.functional_key == action_key,
                ),
            )
            .where(
                DecisionRiskRequirementLinkRecord.tenant_id == tenant_id,
                DecisionRiskRequirementLinkRecord.case_id == case_id,
            )
            .order_by(
                DecisionRiskRequirementLinkRecord.created_at.asc(),
                DecisionRiskRequirementLinkRecord.id.asc(),
            )
            .limit(page_limit + 1)
        )
        if after_created_at is not None and after_id is not None:
            statement = statement.where(
                sa.or_(
                    DecisionRiskRequirementLinkRecord.created_at > after_created_at,
                    sa.and_(
                        DecisionRiskRequirementLinkRecord.created_at == after_created_at,
                        DecisionRiskRequirementLinkRecord.id > after_id,
                    ),
                )
            )

        with self._session_factory() as session:
            rows = session.execute(statement).all()

        has_more = len(rows) > page_limit
        rows = rows[:page_limit]
        items = tuple(
            _link_projection(link, action, state, revision)
            for link, action, state, revision in rows
        )
        next_cursor = (
            _encode_cursor(items[-1].created_at, items[-1].link_id)
            if has_more and items
            else None
        )
        return DecisionRiskRequirementPage(items=items, next_cursor=next_cursor)

    def reconcile(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        link_id: UUID,
        search: str,
        limit: int,
    ) -> tuple[DecisionPricingReconciliationProjection, ...] | None:
        normalized_search = search.strip().casefold()
        with self._session_factory() as session:
            link_exists = session.scalar(
                sa.select(sa.exists().where(
                    DecisionRiskRequirementLinkRecord.tenant_id == tenant_id,
                    DecisionRiskRequirementLinkRecord.case_id == case_id,
                    DecisionRiskRequirementLinkRecord.id == link_id,
                ))
            )
            if not link_exists:
                return None
            search_pattern = f"%{normalized_search}%"
            rows = session.execute(
                sa.select(
                    PricingImportBatchRecord.id,
                    PricingImportBatchRecord.document_kind,
                    PricingImportBatchRecord.state,
                    PricingImportRowRecord.row_number,
                    PricingImportRowRecord.code,
                    PricingImportRowRecord.designation,
                    PricingImportRowRecord.unit,
                )
                .join(
                    PricingImportRowRecord,
                    sa.and_(
                        PricingImportRowRecord.tenant_id == PricingImportBatchRecord.tenant_id,
                        PricingImportRowRecord.batch_id == PricingImportBatchRecord.id,
                    ),
                )
                .where(
                    PricingImportBatchRecord.tenant_id == tenant_id,
                    PricingImportBatchRecord.case_id == case_id,
                    PricingImportBatchRecord.document_kind.in_(["DPGF", "BPU"]),
                    PricingImportBatchRecord.state == "COMMITTED",
                    sa.or_(
                        sa.func.lower(PricingImportRowRecord.code).like(search_pattern),
                        sa.func.lower(PricingImportRowRecord.designation).like(search_pattern),
                    ),
                )
                .order_by(
                    PricingImportBatchRecord.created_at.asc(),
                    PricingImportBatchRecord.id.asc(),
                    PricingImportRowRecord.row_number.asc(),
                )
                .limit(min(limit, 100)),
            ).all()
        return tuple(
            DecisionPricingReconciliationProjection(
                link_id=link_id,
                batch_id=batch_id,
                document_kind=document_kind,
                batch_state=batch_state,
                row_number=row_number,
                code=code,
                designation=designation,
                unit=unit,
                match_basis="CODE_OR_DESIGNATION",
                verification_status="COMMITTED_NORMALIZED_IMPORT",
            )
            for batch_id, document_kind, batch_state, row_number, code, designation, unit in rows
        )


def _link_projection(link, action, state, revision) -> DecisionRiskRequirementLinkProjection:
    return DecisionRiskRequirementLinkProjection(
        link_id=link.id,
        case_id=link.case_id,
        risk_id=link.risk_id,
        requirement_id=link.requirement_id,
        dce_version_id=link.dce_version_id,
        relationship=link.relationship,
        rationale=link.rationale,
        source_refs=tuple(link.source_refs_json),
        created_at=link.created_at,
        action_id=action.id if action is not None else None,
        action_state=state or (action.state if action is not None else None),
        action_severity=action.severity if action is not None else None,
        action_revision=revision or (action.aggregate_revision if action is not None else None),
    )


def _encode_cursor(created_at: datetime, link_id: UUID) -> str:
    payload = f"{created_at.isoformat()}|{link_id}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")

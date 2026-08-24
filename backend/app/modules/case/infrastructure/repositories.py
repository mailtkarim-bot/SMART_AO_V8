"""SQLAlchemy adapter for the Case application port."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.case.application.ports import (
    CaseConsultationLinkSnapshot,
    CaseDceApplicabilitySnapshot,
    CaseRepository,
    CaseRootSnapshot,
    CaseSnapshot,
)
from app.modules.case.infrastructure.models.case import (
    CaseConsultationLinkRecord,
    CaseDceApplicabilityHistoryRecord,
    CaseRecord,
)
from app.platform.persistence.repository import update_root_with_expected_revision


class SqlAlchemyCaseRepository(CaseRepository):
    """Loads and updates only Case state and Case-owned histories."""

    _MUTABLE_ROOT_COLUMNS = frozenset(
        {
            "consultation_id",
            "applicable_dce_version_id",
            "lifecycle",
            "commercial_stage",
            "decision_readiness",
            "dce_freshness",
            "responsibility_status",
            "stopped_reason",
            "stopped_at",
            "archived_reason",
            "archived_at",
            "updated_by_actor_id",
        }
    )

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, *, tenant_id: UUID | str, aggregate_id: UUID | str) -> CaseSnapshot | None:
        root = self._session.scalar(
            sa.select(CaseRecord).where(
                CaseRecord.tenant_id == tenant_id,
                CaseRecord.id == aggregate_id,
            )
        )
        if root is None:
            return None

        consultation_links = tuple(
            CaseConsultationLinkSnapshot(
                id=record.id,
                consultation_id=record.consultation_id,
                scope_snapshot_json=dict(record.scope_snapshot_json),
                rationale=record.rationale,
                is_current=record.is_current,
            )
            for record in self._session.scalars(
                sa.select(CaseConsultationLinkRecord)
                .where(
                    CaseConsultationLinkRecord.tenant_id == tenant_id,
                    CaseConsultationLinkRecord.case_id == aggregate_id,
                )
                .order_by(CaseConsultationLinkRecord.created_at, CaseConsultationLinkRecord.id)
            )
        )
        dce_history = tuple(
            CaseDceApplicabilitySnapshot(
                id=record.id,
                dce_version_id=record.dce_version_id,
                reason=record.reason,
                is_current=record.is_current,
                set_at=record.set_at,
            )
            for record in self._session.scalars(
                sa.select(CaseDceApplicabilityHistoryRecord)
                .where(
                    CaseDceApplicabilityHistoryRecord.tenant_id == tenant_id,
                    CaseDceApplicabilityHistoryRecord.case_id == aggregate_id,
                )
                .order_by(
                    CaseDceApplicabilityHistoryRecord.set_at,
                    CaseDceApplicabilityHistoryRecord.id,
                )
            )
        )
        return CaseSnapshot(
            root=CaseRootSnapshot(
                id=root.id,
                tenant_id=root.tenant_id,
                aggregate_revision=root.aggregate_revision,
                title=root.title,
                object_description=root.object_description,
                business_origin=root.business_origin,
                origin_reference_id=root.origin_reference_id,
                origin_rationale=root.origin_rationale,
                consultation_id=root.consultation_id,
                scope_kind=root.scope_kind,
                scope_json=dict(root.scope_json),
                scope_fingerprint=root.scope_fingerprint,
                applicable_dce_version_id=root.applicable_dce_version_id,
                lifecycle=root.lifecycle,
                commercial_stage=root.commercial_stage,
                decision_readiness=root.decision_readiness,
                dce_freshness=root.dce_freshness,
                responsibility_status=root.responsibility_status,
                stopped_reason=root.stopped_reason,
                stopped_at=root.stopped_at,
                archived_reason=root.archived_reason,
                archived_at=root.archived_at,
            ),
            consultation_links=consultation_links,
            dce_applicability_history=dce_history,
        )

    def has_active_functional_identity(
        self, *, tenant_id: UUID | str, functional_identity_hash: str
    ) -> bool:
        return (
            self._session.scalar(
                sa.select(CaseRecord.id).where(
                    CaseRecord.tenant_id == tenant_id,
                    CaseRecord.functional_identity_hash == functional_identity_hash,
                    CaseRecord.lifecycle != "ARCHIVED",
                )
            )
            is not None
        )

    def create(
        self,
        *,
        aggregate_id: UUID,
        tenant_id: UUID,
        aggregate_revision: int,
        functional_identity_hash: str,
        title: str,
        object_description: str,
        business_origin: str,
        origin_reference_id: UUID | None,
        origin_rationale: str | None,
        consultation_id: UUID | None,
        consultation_scope_snapshot_json: Mapping[str, object] | None,
        consultation_rationale: str | None,
        scope_kind: str,
        scope_json: Mapping[str, object],
        scope_fingerprint: str,
        actor_id: UUID | str,
    ) -> None:
        self._session.add(
            CaseRecord(
                id=aggregate_id,
                tenant_id=tenant_id,
                aggregate_revision=aggregate_revision,
                functional_identity_hash=functional_identity_hash,
                title=title,
                object_description=object_description,
                business_origin=business_origin,
                origin_reference_id=origin_reference_id,
                origin_rationale=origin_rationale,
                consultation_id=consultation_id,
                scope_kind=scope_kind,
                scope_json=dict(scope_json),
                scope_fingerprint=scope_fingerprint,
                applicable_dce_version_id=None,
                lifecycle="ACTIVE",
                commercial_stage="INTAKE",
                decision_readiness="NOT_ASSESSED",
                dce_freshness="NO_DCE",
                responsibility_status="UNASSIGNED",
                stopped_reason=None,
                stopped_at=None,
                archived_reason=None,
                archived_at=None,
                created_by_actor_id=actor_id,
                updated_by_actor_id=actor_id,
            )
        )
        if consultation_id is not None:
            if consultation_scope_snapshot_json is None:
                raise ValueError("CONSULTATION_SCOPE_SNAPSHOT_REQUIRED")
            self._session.add(
                CaseConsultationLinkRecord(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    case_id=aggregate_id,
                    consultation_id=consultation_id,
                    scope_snapshot_json=dict(consultation_scope_snapshot_json),
                    rationale=consultation_rationale,
                    is_current=True,
                    created_by_actor_id=actor_id,
                )
            )

    def update_root(
        self,
        *,
        tenant_id: UUID | str,
        aggregate_id: UUID | str,
        expected_revision: int,
        changes: Mapping[str, object],
    ) -> int:
        return update_root_with_expected_revision(
            self._session,
            table=CaseRecord.__table__,
            tenant_id=tenant_id,
            aggregate_id=aggregate_id,
            expected_revision=expected_revision,
            changes=changes,
            allowed_columns=self._MUTABLE_ROOT_COLUMNS,
        )

"""SQLAlchemy adapters for the Consultation and DceVersion application ports."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.dce.application.ports import (
    ConsultationLotSnapshot,
    ConsultationRepository,
    ConsultationRootSnapshot,
    ConsultationSnapshot,
    ConsultationTrancheSnapshot,
    DceDocumentClassificationSnapshot,
    DceDocumentIssueSnapshot,
    DceDocumentSnapshot,
    DceMissingDocumentSnapshot,
    DceSourceStatementSnapshot,
    DceVersionRepository,
    DceVersionRootSnapshot,
    DceVersionSnapshot,
)
from app.modules.dce.infrastructure.models.consultation import (
    ConsultationLotRecord,
    ConsultationRecord,
    ConsultationTrancheRecord,
)
from app.modules.dce.infrastructure.models.dce_version import (
    DceDocumentClassificationRecord,
    DceDocumentIssueRecord,
    DceDocumentRecord,
    DceMissingDocumentDeclarationRecord,
    DceSourceStatementRecord,
    DceVersionRecord,
)
from app.platform.persistence.repository import update_root_with_expected_revision


class SqlAlchemyConsultationRepository(ConsultationRepository):
    """Loads and updates only Consultation plus its lot/tranche entities."""

    _MUTABLE_ROOT_COLUMNS = frozenset(
        {"lifecycle", "freshness", "metadata_history_json", "updated_by_actor_id"}
    )

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self,
        *,
        tenant_id: UUID | str,
        aggregate_id: UUID | str,
    ) -> ConsultationSnapshot | None:
        root = self._session.scalar(
            sa.select(ConsultationRecord).where(
                ConsultationRecord.tenant_id == tenant_id,
                ConsultationRecord.id == aggregate_id,
            )
        )
        if root is None:
            return None

        lots = tuple(
            ConsultationLotSnapshot(
                id=record.id,
                lot_number=record.lot_number,
                label=record.label,
                source_reference=record.source_reference,
            )
            for record in self._session.scalars(
                sa.select(ConsultationLotRecord)
                .where(
                    ConsultationLotRecord.tenant_id == tenant_id,
                    ConsultationLotRecord.consultation_id == aggregate_id,
                )
                .order_by(ConsultationLotRecord.lot_number, ConsultationLotRecord.id)
            )
        )
        tranches = tuple(
            ConsultationTrancheSnapshot(
                id=record.id,
                tranche_reference=record.tranche_reference,
                tranche_kind=record.tranche_kind,
                label=record.label,
                source_reference=record.source_reference,
            )
            for record in self._session.scalars(
                sa.select(ConsultationTrancheRecord)
                .where(
                    ConsultationTrancheRecord.tenant_id == tenant_id,
                    ConsultationTrancheRecord.consultation_id == aggregate_id,
                )
                .order_by(ConsultationTrancheRecord.tranche_reference, ConsultationTrancheRecord.id)
            )
        )
        return ConsultationSnapshot(
            root=ConsultationRootSnapshot(
                id=root.id,
                tenant_id=root.tenant_id,
                aggregate_revision=root.aggregate_revision,
                functional_identity_hash=root.functional_identity_hash,
                buyer_legal_name=root.buyer_legal_name,
                buyer_normalized_id=root.buyer_normalized_id,
                external_reference=root.external_reference,
                object_label=root.object_label,
                location_label=root.location_label,
                source_channel=root.source_channel,
                source_reference=root.source_reference,
                source_received_at=root.source_received_at,
                lifecycle=root.lifecycle,
                freshness=root.freshness,
                metadata_history_json=tuple(dict(item) for item in root.metadata_history_json),
            ),
            lots=lots,
            tranches=tranches,
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
            table=ConsultationRecord.__table__,
            tenant_id=tenant_id,
            aggregate_id=aggregate_id,
            expected_revision=expected_revision,
            changes=changes,
            allowed_columns=self._MUTABLE_ROOT_COLUMNS,
        )


class SqlAlchemyDceVersionRepository(DceVersionRepository):
    """Loads and updates only DceVersion plus its admitted-document children."""

    _MUTABLE_ROOT_COLUMNS = frozenset(
        {
            "lifecycle",
            "integrity",
            "classification_readiness",
            "analysis_readiness",
            "withdrawal_source",
            "withdrawal_reason",
            "superseded_at",
            "withdrawn_at",
            "updated_by_actor_id",
        }
    )

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, *, tenant_id: UUID | str, aggregate_id: UUID | str) -> DceVersionSnapshot | None:
        root = self._session.scalar(
            sa.select(DceVersionRecord).where(
                DceVersionRecord.tenant_id == tenant_id,
                DceVersionRecord.id == aggregate_id,
            )
        )
        if root is None:
            return None

        documents = tuple(
            DceDocumentSnapshot(
                id=record.id,
                storage_object_id=record.storage_object_id,
                storage_key=record.storage_key,
                original_filename=record.original_filename,
                media_type=record.media_type,
                byte_size=record.byte_size,
                sha256=record.sha256,
                received_from=record.received_from,
            )
            for record in self._session.scalars(
                sa.select(DceDocumentRecord)
                .where(
                    DceDocumentRecord.tenant_id == tenant_id,
                    DceDocumentRecord.dce_version_id == aggregate_id,
                )
                .order_by(DceDocumentRecord.created_at, DceDocumentRecord.id)
            )
        )
        classifications = tuple(
            DceDocumentClassificationSnapshot(
                id=record.id,
                dce_document_id=record.dce_document_id,
                classification=record.classification,
                rationale=record.rationale,
                source=record.source,
                previous_classification_id=record.previous_classification_id,
                is_current=record.is_current,
            )
            for record in self._session.scalars(
                sa.select(DceDocumentClassificationRecord)
                .join(
                    DceDocumentRecord,
                    sa.and_(
                        DceDocumentRecord.tenant_id
                        == DceDocumentClassificationRecord.tenant_id,
                        DceDocumentRecord.id == DceDocumentClassificationRecord.dce_document_id,
                    ),
                )
                .where(
                    DceDocumentClassificationRecord.tenant_id == tenant_id,
                    DceDocumentRecord.dce_version_id == aggregate_id,
                )
                .order_by(
                    DceDocumentClassificationRecord.created_at,
                    DceDocumentClassificationRecord.id,
                )
            )
        )
        issues = tuple(
            DceDocumentIssueSnapshot(
                id=record.id,
                dce_document_id=record.dce_document_id,
                issue_kind=record.issue_kind,
                impact=record.impact,
                locator_json=dict(record.locator_json) if record.locator_json else None,
                reason=record.reason,
            )
            for record in self._session.scalars(
                sa.select(DceDocumentIssueRecord)
                .where(
                    DceDocumentIssueRecord.tenant_id == tenant_id,
                    DceDocumentIssueRecord.dce_version_id == aggregate_id,
                )
                .order_by(DceDocumentIssueRecord.created_at, DceDocumentIssueRecord.id)
            )
        )
        missing_documents = tuple(
            DceMissingDocumentSnapshot(
                id=record.id,
                expected_document_family=record.expected_document_family,
                expectation_source_kind=record.expectation_source_kind,
                expectation_source_id=record.expectation_source_id,
                reason=record.reason,
            )
            for record in self._session.scalars(
                sa.select(DceMissingDocumentDeclarationRecord)
                .where(
                    DceMissingDocumentDeclarationRecord.tenant_id == tenant_id,
                    DceMissingDocumentDeclarationRecord.dce_version_id == aggregate_id,
                )
                .order_by(
                    DceMissingDocumentDeclarationRecord.created_at,
                    DceMissingDocumentDeclarationRecord.id,
                )
            )
        )
        source_statements = tuple(
            DceSourceStatementSnapshot(
                id=record.id,
                dce_document_id=record.dce_document_id,
                locator_json=dict(record.locator_json),
                excerpt=record.excerpt,
                source_language=record.source_language,
                extraction_origin=record.extraction_origin,
            )
            for record in self._session.scalars(
                sa.select(DceSourceStatementRecord)
                .where(
                    DceSourceStatementRecord.tenant_id == tenant_id,
                    DceSourceStatementRecord.dce_version_id == aggregate_id,
                )
                .order_by(DceSourceStatementRecord.created_at, DceSourceStatementRecord.id)
            )
        )
        return DceVersionSnapshot(
            root=DceVersionRootSnapshot(
                id=root.id,
                tenant_id=root.tenant_id,
                aggregate_revision=root.aggregate_revision,
                consultation_id=root.consultation_id,
                corpus_hash=root.corpus_hash,
                predecessor_dce_version_id=root.predecessor_dce_version_id,
                provenance_channel=root.provenance_channel,
                provenance_reference=root.provenance_reference,
                provenance_url=root.provenance_url,
                source_received_at=root.source_received_at,
                lifecycle=root.lifecycle,
                integrity=root.integrity,
                classification_readiness=root.classification_readiness,
                analysis_readiness=root.analysis_readiness,
                withdrawal_source=root.withdrawal_source,
                withdrawal_reason=root.withdrawal_reason,
                superseded_at=root.superseded_at,
                withdrawn_at=root.withdrawn_at,
            ),
            documents=documents,
            classifications=classifications,
            issues=issues,
            missing_documents=missing_documents,
            source_statements=source_statements,
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
            table=DceVersionRecord.__table__,
            tenant_id=tenant_id,
            aggregate_id=aggregate_id,
            expected_revision=expected_revision,
            changes=changes,
            allowed_columns=self._MUTABLE_ROOT_COLUMNS,
        )

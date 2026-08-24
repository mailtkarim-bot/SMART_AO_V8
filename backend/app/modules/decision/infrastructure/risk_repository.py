from __future__ import annotations

from typing import cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.infrastructure.models.dce_extraction import (
    DceDocumentExtractionFragmentRecord,
    DceDocumentExtractionRecord,
)
from app.modules.decision.application.ports import DecisionRiskDraft
from app.modules.decision.infrastructure.models.risk import DecisionRiskRecord


class SqlAlchemyDecisionRiskRepository:
    """SQLAlchemy adapter for the tenant-scoped structured risk register."""

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

    def source_exists(
        self,
        *,
        session: object,
        tenant_id: UUID,
        dce_version_id: UUID,
        source_fragment_id: UUID,
    ) -> bool:
        db_session = cast(Session, session)
        return (
            db_session.scalar(
                sa.select(DceDocumentExtractionFragmentRecord.id)
                .join(
                    DceDocumentExtractionRecord,
                    sa.and_(
                        DceDocumentExtractionRecord.tenant_id
                        == DceDocumentExtractionFragmentRecord.tenant_id,
                        DceDocumentExtractionRecord.id
                        == DceDocumentExtractionFragmentRecord.extraction_id,
                    ),
                )
                .where(
                    DceDocumentExtractionFragmentRecord.tenant_id == tenant_id,
                    DceDocumentExtractionFragmentRecord.id == source_fragment_id,
                    DceDocumentExtractionRecord.dce_version_id == dce_version_id,
                    DceDocumentExtractionRecord.status == "COMPLETED",
                )
            )
            is not None
        )

    def source_supports(
        self,
        *,
        session: object,
        tenant_id: UUID,
        dce_version_id: UUID,
        source_fragment_id: UUID,
        source_excerpt: str,
        start_byte_offset: int,
        end_byte_offset: int,
    ) -> bool:
        db_session = cast(Session, session)
        fragment = db_session.scalar(
            sa.select(DceDocumentExtractionFragmentRecord)
            .join(
                DceDocumentExtractionRecord,
                sa.and_(
                    DceDocumentExtractionRecord.tenant_id
                    == DceDocumentExtractionFragmentRecord.tenant_id,
                    DceDocumentExtractionRecord.id
                    == DceDocumentExtractionFragmentRecord.extraction_id,
                ),
            )
            .where(
                DceDocumentExtractionFragmentRecord.tenant_id == tenant_id,
                DceDocumentExtractionFragmentRecord.id == source_fragment_id,
                DceDocumentExtractionRecord.dce_version_id == dce_version_id,
                DceDocumentExtractionRecord.status == "COMPLETED",
            )
        )
        if fragment is None:
            return False
        text_bytes = fragment.text.encode("utf-8")
        if not 0 <= start_byte_offset < end_byte_offset <= len(text_bytes):
            return False
        try:
            excerpt_at_offsets = text_bytes[start_byte_offset:end_byte_offset].decode("utf-8")
        except UnicodeDecodeError:
            return False
        return excerpt_at_offsets == source_excerpt

    def functional_exists(
        self, *, session: object, tenant_id: UUID, functional_key: str
    ) -> bool:
        db_session = cast(Session, session)
        return (
            db_session.scalar(
                sa.select(DecisionRiskRecord.id).where(
                    DecisionRiskRecord.tenant_id == tenant_id,
                    DecisionRiskRecord.functional_key == functional_key,
                )
            )
            is not None
        )

    def create(self, *, session: object, draft: DecisionRiskDraft) -> None:
        db_session = cast(Session, session)
        draft.risk.validate()
        db_session.add(
            DecisionRiskRecord(
                id=draft.id,
                tenant_id=draft.tenant_id,
                case_id=draft.case_id,
                dce_version_id=draft.dce_version_id,
                source_fragment_id=draft.source_fragment_id,
                functional_key=draft.functional_key,
                category=draft.risk.category.value,
                risk_code=draft.risk.risk_code,
                title=draft.risk.title,
                statement=draft.risk.statement,
                severity=draft.risk.severity.value,
                likelihood=draft.risk.likelihood.value,
                treatment=draft.risk.treatment.value,
                source_excerpt=draft.risk.source_excerpt,
                source_locator_json=draft.risk.source_locator,
                start_byte_offset=draft.risk.start_byte_offset,
                end_byte_offset=draft.risk.end_byte_offset,
                actor_id=draft.actor_id,
                membership_id=draft.membership_id,
                command_id=draft.command_id,
                idempotency_key=draft.idempotency_key,
                correlation_id=draft.correlation_id,
                due_at=draft.due_at,
            )
        )

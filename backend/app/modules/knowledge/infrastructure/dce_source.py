from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.infrastructure.models.dce_extraction import (
    DceDocumentExtractionFragmentRecord,
    DceDocumentExtractionRecord,
)
from app.modules.knowledge.domain.retrieval import DataClassification, RetrievalChunk


class SqlAlchemyDceRetrievalSource:
    """Reads only completed fragments for the case's current DCE version."""

    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def read_chunks(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        dce_version_id: UUID,
    ) -> Sequence[RetrievalChunk]:
        with self._session_factory() as session:
            rows = session.execute(
                sa.select(
                    DceDocumentExtractionFragmentRecord,
                    DceDocumentExtractionRecord,
                )
                .join(
                    DceDocumentExtractionRecord,
                    sa.and_(
                        DceDocumentExtractionRecord.tenant_id
                        == DceDocumentExtractionFragmentRecord.tenant_id,
                        DceDocumentExtractionRecord.id
                        == DceDocumentExtractionFragmentRecord.extraction_id,
                    ),
                )
                .join(
                    CaseRecord,
                    sa.and_(
                        CaseRecord.tenant_id == DceDocumentExtractionRecord.tenant_id,
                        CaseRecord.id == case_id,
                        CaseRecord.applicable_dce_version_id
                        == DceDocumentExtractionRecord.dce_version_id,
                    ),
                )
                .where(
                    DceDocumentExtractionFragmentRecord.tenant_id == tenant_id,
                    DceDocumentExtractionRecord.dce_version_id == dce_version_id,
                    DceDocumentExtractionRecord.status == "COMPLETED",
                )
                .order_by(
                    DceDocumentExtractionFragmentRecord.ordinal,
                    DceDocumentExtractionFragmentRecord.id,
                )
            ).all()

        return tuple(
            RetrievalChunk(
                chunk_id=fragment.id,
                tenant_id=fragment.tenant_id,
                case_id=case_id,
                dce_version_id=extraction.dce_version_id,
                source_fragment_id=fragment.id,
                ordinal=fragment.ordinal,
                text=fragment.text,
                locator=fragment.locator_json,
                classification=DataClassification.INTERNAL_OPERATIONAL,
            )
            for fragment, extraction in rows
        )

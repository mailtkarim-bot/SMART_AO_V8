from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.infrastructure.models.dce_extraction import (
    DceDocumentExtractionFragmentRecord,
    DceDocumentExtractionRecord,
)
from app.modules.dce.infrastructure.models.dce_version import (
    DceDocumentClassificationRecord,
    DceDocumentRecord,
)
from app.modules.decision.application.queries import (
    DecisionCctpPricingCrossingProjection,
)
from app.modules.decision.domain.pricing_crossing import match_cctp_to_pricing_row
from app.modules.pricing.infrastructure.models.financial import (
    PricingImportBatchRecord,
    PricingImportRowRecord,
)


class SqlAlchemyDecisionCctpPricingCrossingReader:
    """Read-only deterministic crossing of CCTP fragments with normalized price rows."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def cross(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        limit: int,
    ) -> tuple[DecisionCctpPricingCrossingProjection, ...]:
        page_limit = min(max(limit, 1), 100)
        with self._session_factory() as session:
            dce_version_id = session.scalar(
                sa.select(CaseRecord.applicable_dce_version_id).where(
                    CaseRecord.tenant_id == tenant_id,
                    CaseRecord.id == case_id,
                )
            )
            if dce_version_id is None:
                return ()

            fragments = session.execute(
                sa.select(
                    DceDocumentExtractionFragmentRecord.id,
                    DceDocumentExtractionFragmentRecord.ordinal,
                    DceDocumentExtractionFragmentRecord.locator_json,
                    DceDocumentExtractionFragmentRecord.text,
                )
                .select_from(DceDocumentExtractionFragmentRecord)
                .join(
                    DceDocumentExtractionRecord,
                    sa.and_(
                        DceDocumentExtractionRecord.tenant_id == tenant_id,
                        DceDocumentExtractionRecord.id
                        == DceDocumentExtractionFragmentRecord.extraction_id,
                        DceDocumentExtractionRecord.dce_version_id == dce_version_id,
                        DceDocumentExtractionRecord.status == "COMPLETED",
                    ),
                )
                .join(
                    DceDocumentRecord,
                    sa.and_(
                        DceDocumentRecord.tenant_id == tenant_id,
                        DceDocumentRecord.id == DceDocumentExtractionRecord.dce_document_id,
                    ),
                )
                .join(
                    DceDocumentClassificationRecord,
                    sa.and_(
                        DceDocumentClassificationRecord.tenant_id == tenant_id,
                        DceDocumentClassificationRecord.dce_document_id == DceDocumentRecord.id,
                        DceDocumentClassificationRecord.is_current.is_(True),
                        DceDocumentClassificationRecord.classification == "CCTP",
                    ),
                )
                .where(
                    DceDocumentExtractionFragmentRecord.tenant_id == tenant_id,
                )
                .order_by(
                    DceDocumentExtractionFragmentRecord.id.asc(),
                )
            ).all()

            rows = session.execute(
                sa.select(
                    PricingImportBatchRecord.id,
                    PricingImportBatchRecord.document_kind,
                    PricingImportRowRecord.row_number,
                    PricingImportRowRecord.code,
                    PricingImportRowRecord.designation,
                    PricingImportRowRecord.unit,
                )
                .select_from(PricingImportBatchRecord)
                .join(
                    PricingImportRowRecord,
                    sa.and_(
                        PricingImportRowRecord.tenant_id == tenant_id,
                        PricingImportRowRecord.batch_id == PricingImportBatchRecord.id,
                    ),
                )
                .where(
                    PricingImportBatchRecord.tenant_id == tenant_id,
                    PricingImportBatchRecord.case_id == case_id,
                    PricingImportBatchRecord.document_kind.in_(("DPGF", "BPU")),
                    PricingImportBatchRecord.state == "COMMITTED",
                )
                .order_by(
                    PricingImportBatchRecord.id.asc(),
                    PricingImportRowRecord.row_number.asc(),
                )
            ).all()

        candidates: list[DecisionCctpPricingCrossingProjection] = []
        for fragment_id, _ordinal, locator_json, text in fragments:
            for batch_id, document_kind, row_number, code, designation, unit in rows:
                match = match_cctp_to_pricing_row(
                    cctp_text=text,
                    code=code,
                    designation=designation,
                    unit=unit,
                )
                if match is None:
                    continue
                start_offset = 0
                end_offset = len(text.encode("utf-8"))
                candidates.append(
                    DecisionCctpPricingCrossingProjection(
                        dce_version_id=dce_version_id,
                        source_fragment_id=fragment_id,
                        source_locator_label=_source_locator_label(locator_json),
                        source_start_byte_offset=start_offset,
                        source_end_byte_offset=end_offset,
                        batch_id=batch_id,
                        document_kind=document_kind,
                        row_number=row_number,
                        code=code,
                        designation=designation,
                        unit=unit,
                        match_score_bps=match.score_bps,
                        match_basis=match.match_basis,
                        verification_status="REVIEW_REQUIRED",
                    )
                )

        candidates.sort(
            key=lambda item: (
                -item.match_score_bps,
                item.document_kind,
                str(item.batch_id),
                item.row_number,
                str(item.source_fragment_id),
            )
        )
        return tuple(candidates[:page_limit])


def _source_locator_label(locator_json: object) -> str:
    if not isinstance(locator_json, dict):
        return "CCTP · localisation indisponible"
    kind = locator_json.get("kind")
    if kind == "pdf_page" and _positive_int(locator_json.get("page")):
        return f"CCTP · page {locator_json['page']}"
    if kind == "docx_paragraph" and _positive_int(locator_json.get("paragraph")):
        return f"CCTP · paragraphe {locator_json['paragraph']}"
    if kind == "text_line" and _positive_int(locator_json.get("line")):
        return f"CCTP · ligne {locator_json['line']}"
    return "CCTP · localisation indisponible"


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0

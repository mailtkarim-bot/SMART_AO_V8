from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.queries import DceContractRiskSignalProjection
from app.modules.dce.infrastructure.models.dce_extraction import (
    DceDocumentExtractionFragmentRecord,
    DceDocumentExtractionRecord,
)
from app.modules.dce.infrastructure.models.dce_rc_analysis import (
    DceRcAnalysisRunRecord,
    DceRcRequirementObservationRecord,
    DceRcRequirementSourceRecord,
)
from app.modules.dce.infrastructure.models.dce_version import (
    DceDocumentClassificationRecord,
    DceDocumentRecord,
)

_CONTRACT_RISK_KINDS = (
    "CCAP_PENALTIES",
    "CCAP_RETENTION_GUARANTEE",
    "CCAP_GUARANTEE",
    "CCAP_INSURANCE",
    "CCTP_VARIANTS",
    "CCAP_SUBCONTRACTING",
    "CCAP_QUALIFICATIONS",
)


class SqlAlchemyDceContractRiskSignalReader:
    """Read-only tenant-scoped projection of persisted CCAP/CCTP signals."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_for_case(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        limit: int,
    ) -> tuple[DceContractRiskSignalProjection, ...]:
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
            analysis_id = session.scalar(
                sa.select(DceRcAnalysisRunRecord.id)
                .where(
                    DceRcAnalysisRunRecord.tenant_id == tenant_id,
                    DceRcAnalysisRunRecord.dce_version_id == dce_version_id,
                    DceRcAnalysisRunRecord.status == "COMPLETED",
                )
                .order_by(
                    DceRcAnalysisRunRecord.created_at.desc(),
                    DceRcAnalysisRunRecord.id.desc(),
                )
                .limit(1)
            )
            if analysis_id is None:
                return ()
            rows = session.execute(
                sa.select(
                    DceRcRequirementObservationRecord.id,
                    DceRcRequirementObservationRecord.dce_version_id,
                    DceRcRequirementObservationRecord.requirement_kind,
                    DceRcRequirementObservationRecord.rule_id,
                    DceRcRequirementObservationRecord.rule_version,
                    DceRcRequirementObservationRecord.directive,
                    DceRcRequirementObservationRecord.fragment_id,
                    DceRcRequirementObservationRecord.start_byte_offset,
                    DceRcRequirementObservationRecord.end_byte_offset,
                    DceDocumentExtractionFragmentRecord.locator_json,
                    DceDocumentClassificationRecord.classification,
                )
                .select_from(DceRcRequirementObservationRecord)
                .join(
                    DceRcRequirementSourceRecord,
                    sa.and_(
                        DceRcRequirementSourceRecord.tenant_id == tenant_id,
                        DceRcRequirementSourceRecord.observation_id
                        == DceRcRequirementObservationRecord.id,
                        DceRcRequirementSourceRecord.fragment_id
                        == DceRcRequirementObservationRecord.fragment_id,
                    ),
                )
                .join(
                    DceDocumentExtractionFragmentRecord,
                    sa.and_(
                        DceDocumentExtractionFragmentRecord.tenant_id == tenant_id,
                        DceDocumentExtractionFragmentRecord.id
                        == DceRcRequirementSourceRecord.fragment_id,
                    ),
                )
                .join(
                    DceDocumentExtractionRecord,
                    sa.and_(
                        DceDocumentExtractionRecord.tenant_id == tenant_id,
                        DceDocumentExtractionRecord.id
                        == DceDocumentExtractionFragmentRecord.extraction_id,
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
                        DceDocumentClassificationRecord.classification.in_(("CCAP", "CCTP")),
                    ),
                )
                .where(
                    DceRcRequirementObservationRecord.tenant_id == tenant_id,
                    DceRcRequirementObservationRecord.analysis_id == analysis_id,
                    DceRcRequirementObservationRecord.dce_version_id == dce_version_id,
                    DceRcRequirementObservationRecord.requirement_kind.in_(_CONTRACT_RISK_KINDS),
                )
                .order_by(
                    DceRcRequirementObservationRecord.fragment_id.asc(),
                    DceRcRequirementObservationRecord.start_byte_offset.asc(),
                    DceRcRequirementObservationRecord.rule_id.asc(),
                    DceRcRequirementObservationRecord.id.asc(),
                )
                .limit(page_limit)
            ).all()

        return tuple(
            DceContractRiskSignalProjection(
                observation_id=observation_id,
                dce_version_id=row_dce_version_id,
                document_family=classification,
                requirement_kind=requirement_kind,
                rule_id=rule_id,
                rule_version=rule_version,
                directive=directive,
                fragment_id=fragment_id,
                source_locator_label=_source_locator_label(locator_json, classification),
                start_byte_offset=start_offset,
                end_byte_offset=end_offset,
                verification_status="REVIEW_REQUIRED",
            )
            for (
                observation_id,
                row_dce_version_id,
                requirement_kind,
                rule_id,
                rule_version,
                directive,
                fragment_id,
                start_offset,
                end_offset,
                locator_json,
                classification,
            ) in rows
        )


def _source_locator_label(locator_json: object, document_family: str) -> str:
    if not isinstance(locator_json, dict):
        return f"{document_family} · localisation indisponible"
    kind = locator_json.get("kind")
    if kind == "pdf_page" and _positive_int(locator_json.get("page")):
        return f"{document_family} · page {locator_json['page']}"
    if kind == "docx_paragraph" and _positive_int(locator_json.get("paragraph")):
        return f"{document_family} · paragraphe {locator_json['paragraph']}"
    if kind == "text_line" and _positive_int(locator_json.get("line")):
        return f"{document_family} · ligne {locator_json['line']}"
    return f"{document_family} · localisation indisponible"


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0

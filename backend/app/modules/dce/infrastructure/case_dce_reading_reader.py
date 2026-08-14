"""Tenant-scoped closed read adapter for the DCE applicable to one Case."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.queries import (
    CaseDceReadingAvailability,
    CaseDceReadingCounters,
    CaseDceReadingLookup,
    CaseDceReadingProjection,
    CaseDceReadingReader,
    CaseDceReadingRequirementProjection,
)
from app.modules.dce.infrastructure.models.dce_extraction import (
    DceDocumentExtractionFragmentRecord,
    DceDocumentExtractionRecord,
)
from app.modules.dce.infrastructure.models.dce_requirement_confirmations import (
    DceRequirementConfirmationCurrentRecord,
)
from app.modules.dce.infrastructure.models.dce_requirements import (
    DceRequirementRecord,
    DceRequirementSourceRecord,
)
from app.modules.dce.infrastructure.models.dce_version import (
    DceDocumentClassificationRecord,
    DceDocumentRecord,
    DceVersionRecord,
)

_SAFE_DOCUMENT_FAMILIES: Final[frozenset[str]] = frozenset(
    {
        "RC",
        "CCAP",
        "CCTP",
        "AE",
        "BPU",
        "DPGF",
        "PLAN",
        "ANNEX",
        "RECTIFICATION",
    }
)
_SOURCE_UNCLASSIFIED: Final[str] = "SOURCE_UNCLASSIFIED"
_SOURCE_LOCALIZED: Final[str] = "Source localisée"
_PENDING_HUMAN_CONFIRMATION: Final[str] = "PENDING_HUMAN_CONFIRMATION"


class SqlAlchemyCaseDceReadingReader(CaseDceReadingReader):
    """Rebuild the closed DCE reading view for one Case from source registers.

    This adapter never returns document content, storage metadata, hashes, audit
    facts, financial information, or current-confirmation authors.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self,
        *,
        tenant_id: UUID | str,
        case_id: UUID | str,
    ) -> CaseDceReadingLookup | None:
        case = self._session.scalar(
            sa.select(CaseRecord).where(
                CaseRecord.tenant_id == tenant_id,
                CaseRecord.id == case_id,
            )
        )
        if case is None:
            return None

        if case.applicable_dce_version_id is None:
            return self._unavailable_lookup(
                case=case,
                availability=CaseDceReadingAvailability.NO_APPLICABLE_DCE,
            )

        dce = self._session.scalar(
            sa.select(DceVersionRecord).where(
                DceVersionRecord.tenant_id == tenant_id,
                DceVersionRecord.id == case.applicable_dce_version_id,
            )
        )
        if dce is None:
            return self._unavailable_lookup(
                case=case,
                availability=CaseDceReadingAvailability.DCE_REFERENCE_BROKEN,
            )

        requirements = self._read_requirements(tenant_id=tenant_id, dce_version_id=dce.id)
        counters = self._counters(requirements)
        return CaseDceReadingLookup(
            case_id=case.id,
            work_label=case.title,
            case_lifecycle=case.lifecycle,
            commercial_stage=case.commercial_stage,
            dce_freshness=case.dce_freshness,
            availability=CaseDceReadingAvailability.AVAILABLE,
            reading=CaseDceReadingProjection(
                dce_version_id=dce.id,
                lifecycle=dce.lifecycle,
                integrity=dce.integrity,
                classification_readiness=dce.classification_readiness,
                analysis_readiness=dce.analysis_readiness,
                source_received_at=dce.source_received_at,
                requirements=requirements,
                counters=counters,
            ),
        )

    @staticmethod
    def _unavailable_lookup(
        *,
        case: CaseRecord,
        availability: CaseDceReadingAvailability,
    ) -> CaseDceReadingLookup:
        return CaseDceReadingLookup(
            case_id=case.id,
            work_label=case.title,
            case_lifecycle=case.lifecycle,
            commercial_stage=case.commercial_stage,
            dce_freshness=case.dce_freshness,
            availability=availability,
            reading=None,
        )

    def _read_requirements(
        self,
        *,
        tenant_id: UUID | str,
        dce_version_id: UUID,
    ) -> tuple[CaseDceReadingRequirementProjection, ...]:
        rows = self._session.execute(
            sa.select(
                DceRequirementRecord.id,
                DceRequirementRecord.requirement_type,
                DceRequirementRecord.directive_signal,
                DceRequirementRecord.uncertainty_status,
                DceRequirementConfirmationCurrentRecord.outcome,
                DceDocumentClassificationRecord.classification,
                DceDocumentExtractionFragmentRecord.locator_json,
            )
            .select_from(DceRequirementRecord)
            .outerjoin(
                DceRequirementConfirmationCurrentRecord,
                sa.and_(
                    DceRequirementConfirmationCurrentRecord.tenant_id == tenant_id,
                    DceRequirementConfirmationCurrentRecord.requirement_id
                    == DceRequirementRecord.id,
                ),
            )
            .outerjoin(
                DceRequirementSourceRecord,
                sa.and_(
                    DceRequirementSourceRecord.tenant_id == tenant_id,
                    DceRequirementSourceRecord.requirement_id == DceRequirementRecord.id,
                ),
            )
            .outerjoin(
                DceDocumentExtractionFragmentRecord,
                sa.and_(
                    DceDocumentExtractionFragmentRecord.tenant_id == tenant_id,
                    DceDocumentExtractionFragmentRecord.id
                    == DceRequirementSourceRecord.fragment_id,
                ),
            )
            .outerjoin(
                DceDocumentExtractionRecord,
                sa.and_(
                    DceDocumentExtractionRecord.tenant_id == tenant_id,
                    DceDocumentExtractionRecord.id
                    == DceDocumentExtractionFragmentRecord.extraction_id,
                ),
            )
            .outerjoin(
                DceDocumentRecord,
                sa.and_(
                    DceDocumentRecord.tenant_id == tenant_id,
                    DceDocumentRecord.id == DceDocumentExtractionRecord.dce_document_id,
                ),
            )
            .outerjoin(
                DceDocumentClassificationRecord,
                sa.and_(
                    DceDocumentClassificationRecord.tenant_id == tenant_id,
                    DceDocumentClassificationRecord.dce_document_id == DceDocumentRecord.id,
                    DceDocumentClassificationRecord.is_current.is_(True),
                ),
            )
            .where(
                DceRequirementRecord.tenant_id == tenant_id,
                DceRequirementRecord.dce_version_id == dce_version_id,
            )
            .order_by(
                DceRequirementRecord.requirement_type,
                DceRequirementRecord.id,
            )
        ).all()

        projections = tuple(
            self._requirement_projection(
                requirement_id=row.id,
                requirement_type=row.requirement_type,
                directive_signal=row.directive_signal,
                uncertainty_status=row.uncertainty_status,
                confirmation_outcome=row.outcome,
                classification=row.classification,
                locator_json=row.locator_json,
            )
            for row in rows
        )
        return tuple(
            sorted(
                projections,
                key=lambda item: (
                    item.requirement_type,
                    item.source_locator_label,
                    str(item.requirement_id),
                ),
            )
        )

    @staticmethod
    def _requirement_projection(
        *,
        requirement_id: UUID,
        requirement_type: str,
        directive_signal: str,
        uncertainty_status: str,
        confirmation_outcome: str | None,
        classification: str | None,
        locator_json: object,
    ) -> CaseDceReadingRequirementProjection:
        document_family = _safe_document_family(classification)
        return CaseDceReadingRequirementProjection(
            requirement_id=requirement_id,
            requirement_type=requirement_type,
            directive_signal=directive_signal,
            confirmation_outcome=confirmation_outcome or _PENDING_HUMAN_CONFIRMATION,
            uncertainty_status=uncertainty_status,
            document_family=document_family,
            source_locator_label=_source_locator_label(
                document_family=document_family,
                locator_json=locator_json,
            ),
        )

    @staticmethod
    def _counters(
        requirements: Iterable[CaseDceReadingRequirementProjection],
    ) -> CaseDceReadingCounters:
        materialized = tuple(requirements)
        outcomes = tuple(item.confirmation_outcome for item in materialized)
        return CaseDceReadingCounters(
            total=len(materialized),
            pending_human_confirmation=outcomes.count(_PENDING_HUMAN_CONFIRMATION),
            confirmed=outcomes.count("CONFIRMED"),
            review_required=outcomes.count("REVIEW_REQUIRED"),
            not_applicable=outcomes.count("NOT_APPLICABLE"),
        )


def _safe_document_family(classification: str | None) -> str:
    """Return only the closed family vocabulary used by the reading view."""

    if classification in _SAFE_DOCUMENT_FAMILIES:
        return classification
    return _SOURCE_UNCLASSIFIED


def _source_locator_label(*, document_family: str, locator_json: object) -> str:
    """Format a bounded human locator without returning locator JSON or source text."""

    if not isinstance(locator_json, dict):
        return _SOURCE_LOCALIZED

    kind = locator_json.get("kind")
    if kind == "pdf_page":
        page = locator_json.get("page")
        if _positive_int(page):
            return f"{document_family} · page {page}"
    if kind == "docx_paragraph":
        paragraph = locator_json.get("paragraph")
        if _positive_int(paragraph):
            return f"{document_family} · paragraphe {paragraph}"
    if kind == "text_line":
        line = locator_json.get("line")
        if _positive_int(line):
            return f"{document_family} · ligne {line}"
    if kind == "xlsx_cell":
        sheet = locator_json.get("sheet")
        cell = locator_json.get("cell")
        if _safe_locator_token(sheet, maximum_length=80) and _safe_locator_token(
            cell, maximum_length=16
        ):
            return f"{document_family} · cellule {sheet}!{cell}"
    return _SOURCE_LOCALIZED


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _safe_locator_token(value: object, *, maximum_length: int) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= maximum_length
        and "\n" not in value
        and "\r" not in value
    )

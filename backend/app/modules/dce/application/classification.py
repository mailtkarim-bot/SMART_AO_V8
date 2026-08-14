"""Deterministic, source-bound DCE document classification over immutable fragments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Final
from uuid import UUID, uuid5

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.dce.application.commands import (
    DceDocumentClassificationEvidenceInput,
    DceDocumentClassificationResultInput,
    RecordDceDocumentClassificationRunCommand,
)
from app.modules.dce.infrastructure.models.dce_classification import (
    DceDocumentClassificationRunRecord,
)
from app.modules.dce.infrastructure.models.dce_extraction import (
    DceDocumentExtractionFragmentRecord,
    DceDocumentExtractionRecord,
)
from app.modules.dce.infrastructure.models.dce_version import DceDocumentRecord, DceVersionRecord
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, DispatchResult

CLASSIFIER_ID: Final = "smart-ao-document-rules"
CLASSIFIER_VERSION: Final = "1"
SYSTEM_CLASSIFICATION_ACTOR_ID: Final = UUID("00000000-0000-0000-0000-000000000015")
MAX_DOCUMENTS: Final = 10_000
MAX_SOURCE_FRAGMENTS: Final = 100_000
MAX_SOURCE_CHARS: Final = 10_000_000
MAX_EVIDENCE_PER_DOCUMENT: Final = 20
MAX_EXCERPT_CHARS: Final = 1_000


@dataclass(frozen=True, slots=True)
class ClassificationFragment:
    """Trusted text fragment from one completed extraction of an admitted document."""

    extraction_id: UUID
    fragment_id: UUID
    ordinal: int
    text: str
    text_sha256: str


@dataclass(frozen=True, slots=True)
class ClassificationDocument:
    """One immutable DCE document with all its completed extraction fragments."""

    dce_document_id: UUID
    fragments: tuple[ClassificationFragment, ...]


@dataclass(frozen=True, slots=True)
class ClassificationEvidence:
    """One lexical rule match and its exact bounded source location."""

    fragment_id: UUID
    rule_id: str
    start_byte_offset: int
    end_byte_offset: int
    excerpt: str


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Terminal classification outcome for one document in a DCE run."""

    dce_document_id: UUID
    status: str
    classification: str | None
    rule_match_count: int
    evidence: tuple[ClassificationEvidence, ...]


@dataclass(frozen=True, slots=True)
class ClassificationProjection:
    """Terminal full-DCE classification projection ready for durable recording."""

    status: str
    failure_code: str | None
    documents: tuple[ClassificationDocument, ...]
    results: tuple[ClassificationResult, ...]
    source_fragment_count: int
    source_char_count: int


@dataclass(frozen=True, slots=True)
class _ClassificationRule:
    classification: str
    rule_id: str
    pattern: re.Pattern[str]


_CLASSIFICATION_RULES: Final = (
    _ClassificationRule(
        "RC",
        "DOCUMENT_RC_TITLE_V1",
        re.compile(
            r"\brèglement\s+de\s+la\s+consultation\b|\brèglement\s+de\s+consultation\b",
            re.IGNORECASE,
        ),
    ),
    _ClassificationRule(
        "CCAP",
        "DOCUMENT_CCAP_TITLE_V1",
        re.compile(
            r"\bCCAP\b|\bcahier\s+des\s+clauses\s+administratives\s+particulières\b",
            re.IGNORECASE,
        ),
    ),
    _ClassificationRule(
        "CCTP",
        "DOCUMENT_CCTP_TITLE_V1",
        re.compile(
            r"\bCCTP\b|\bcahier\s+des\s+clauses\s+techniques\s+particulières\b",
            re.IGNORECASE,
        ),
    ),
    _ClassificationRule(
        "AE",
        "DOCUMENT_AE_TITLE_V1",
        re.compile(r"\bacte\s+d['’]engagement\b", re.IGNORECASE),
    ),
    _ClassificationRule(
        "BPU",
        "DOCUMENT_BPU_TITLE_V1",
        re.compile(r"\bBPU\b|\bbordereau\s+de\s+prix\s+unitaires\b", re.IGNORECASE),
    ),
    _ClassificationRule(
        "DPGF",
        "DOCUMENT_DPGF_TITLE_V1",
        re.compile(
            r"\bDPGF\b|\bdécomposition\s+du\s+prix\s+global\s+et\s+forfaitaire\b",
            re.IGNORECASE,
        ),
    ),
    _ClassificationRule(
        "PLAN",
        "DOCUMENT_PLAN_REFERENCE_V1",
        re.compile(
            r"\bplan\s+(?:de\s+situation|d['’]installation|d['’]implantation)\b",
            re.IGNORECASE,
        ),
    ),
    _ClassificationRule(
        "ANNEX",
        "DOCUMENT_ANNEX_REFERENCE_V1",
        re.compile(r"\bannexe(?:s)?\b", re.IGNORECASE),
    ),
    _ClassificationRule(
        "RECTIFICATION",
        "DOCUMENT_RECTIFICATION_REFERENCE_V1",
        re.compile(r"\brectificatif\b|\bmodification\s+de\s+la\s+consultation\b", re.IGNORECASE),
    ),
)


class DceDocumentClassificationService:
    """Classify one full admitted DCE without reading originals or making business decisions."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        dispatcher: CommandDispatcher,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher

    def classify(
        self,
        *,
        tenant_id: UUID,
        dce_version_id: UUID,
        now: datetime | None = None,
    ) -> DispatchResult:
        effective_now = now or datetime.now(tz=UTC)
        expected_revision, documents = self._load_documents(
            tenant_id=tenant_id,
            dce_version_id=dce_version_id,
        )
        projection = project_dce_classification(documents=documents)
        command = _recording_command(
            dce_version_id=dce_version_id,
            expected_dce_version_revision=expected_revision,
            projection=projection,
        )
        return self._dispatcher.dispatch(
            command=command,
            context=CommandContext(
                tenant_id=tenant_id,
                actor_id=SYSTEM_CLASSIFICATION_ACTOR_ID,
                actor_kind="SYSTEM",
                received_at=effective_now,
            ),
        )

    def _load_documents(
        self,
        *,
        tenant_id: UUID,
        dce_version_id: UUID,
    ) -> tuple[int, tuple[ClassificationDocument, ...]]:
        with self._session_factory() as session:
            dce_version = session.scalar(
                select(DceVersionRecord).where(
                    DceVersionRecord.tenant_id == tenant_id,
                    DceVersionRecord.id == dce_version_id,
                )
            )
            if (
                dce_version is None
                or dce_version.lifecycle not in {"ADMITTED", "SUPERSEDED"}
                or dce_version.integrity != "VERIFIED"
            ):
                raise ValueError("DCE_VERSION_NOT_CLASSIFIABLE")
            document_ids = list(
                session.scalars(
                    select(DceDocumentRecord.id)
                    .where(
                        DceDocumentRecord.tenant_id == tenant_id,
                        DceDocumentRecord.dce_version_id == dce_version_id,
                    )
                    .order_by(DceDocumentRecord.id)
                )
            )
            if not document_ids:
                raise ValueError("DCE_DOCUMENT_REQUIRED")
            rows = session.execute(
                select(
                    DceDocumentExtractionRecord.dce_document_id,
                    DceDocumentExtractionRecord.id,
                    DceDocumentExtractionFragmentRecord,
                )
                .join(
                    DceDocumentExtractionFragmentRecord,
                    and_(
                        DceDocumentExtractionFragmentRecord.tenant_id
                        == DceDocumentExtractionRecord.tenant_id,
                        DceDocumentExtractionFragmentRecord.extraction_id
                        == DceDocumentExtractionRecord.id,
                    ),
                )
                .where(
                    DceDocumentExtractionRecord.tenant_id == tenant_id,
                    DceDocumentExtractionRecord.dce_document_id.in_(document_ids),
                    DceDocumentExtractionRecord.status == "COMPLETED",
                )
                .order_by(
                    DceDocumentExtractionRecord.dce_document_id,
                    DceDocumentExtractionRecord.id,
                    DceDocumentExtractionFragmentRecord.ordinal,
                    DceDocumentExtractionFragmentRecord.id,
                )
            ).all()
            fragments_by_document: dict[UUID, list[ClassificationFragment]] = {
                document_id: [] for document_id in document_ids
            }
            for document_id, extraction_id, fragment in rows:
                fragments_by_document[document_id].append(
                    ClassificationFragment(
                        extraction_id=extraction_id,
                        fragment_id=fragment.id,
                        ordinal=fragment.ordinal,
                        text=fragment.text,
                        text_sha256=fragment.text_sha256,
                    )
                )
            documents = tuple(
                ClassificationDocument(
                    dce_document_id=document_id,
                    fragments=tuple(fragments_by_document[document_id]),
                )
                for document_id in document_ids
            )
            existing_run = session.scalar(
                select(DceDocumentClassificationRunRecord).where(
                    DceDocumentClassificationRunRecord.tenant_id == tenant_id,
                    DceDocumentClassificationRunRecord.dce_version_id == dce_version_id,
                    DceDocumentClassificationRunRecord.input_manifest_sha256
                    == classification_input_manifest_sha256(documents=documents),
                    DceDocumentClassificationRunRecord.classifier_id == CLASSIFIER_ID,
                    DceDocumentClassificationRunRecord.classifier_version == CLASSIFIER_VERSION,
                )
            )
            return (
                existing_run.dce_version_revision_before
                if existing_run is not None
                else dce_version.aggregate_revision,
                documents,
            )


def is_valid_document_classification_evidence(
    *,
    classification: str,
    rule_id: str,
    excerpt: str,
) -> bool:
    """Return whether one persisted proof reproduces its family and rule from its excerpt."""

    for rule in _CLASSIFICATION_RULES:
        if rule.classification != classification or rule.rule_id != rule_id:
            continue
        return rule.pattern.search(excerpt) is not None
    return False


def project_dce_classification(
    *,
    documents: tuple[ClassificationDocument, ...],
) -> ClassificationProjection:
    source_fragment_count = sum(len(document.fragments) for document in documents)
    source_char_count = sum(
        len(fragment.text) for document in documents for fragment in document.fragments
    )
    if (
        len(documents) > MAX_DOCUMENTS
        or source_fragment_count > MAX_SOURCE_FRAGMENTS
        or source_char_count > MAX_SOURCE_CHARS
    ):
        return ClassificationProjection(
            status="REJECTED_LIMIT",
            failure_code="CLASSIFICATION_LIMIT",
            documents=documents,
            results=(),
            source_fragment_count=source_fragment_count,
            source_char_count=source_char_count,
        )

    results = tuple(_classify_document(document=document) for document in documents)
    return ClassificationProjection(
        status="COMPLETED",
        failure_code=None,
        documents=documents,
        results=results,
        source_fragment_count=source_fragment_count,
        source_char_count=source_char_count,
    )


def _classify_document(*, document: ClassificationDocument) -> ClassificationResult:
    if not document.fragments:
        return ClassificationResult(
            dce_document_id=document.dce_document_id,
            status="NOT_EXTRACTED",
            classification=None,
            rule_match_count=0,
            evidence=(),
        )
    evidence_by_classification: dict[str, list[ClassificationEvidence]] = {}
    evidence_keys: set[tuple[str, UUID, int, int]] = set()
    scores: dict[str, int] = {}
    for fragment in document.fragments:
        for rule in _CLASSIFICATION_RULES:
            matches = list(rule.pattern.finditer(fragment.text))
            if not matches:
                continue
            scores[rule.classification] = scores.get(rule.classification, 0) + len(matches)
            evidence = evidence_by_classification.setdefault(rule.classification, [])
            for match in matches:
                if len(evidence) >= MAX_EVIDENCE_PER_DOCUMENT:
                    continue
                start_byte_offset, end_byte_offset, excerpt = _bounded_excerpt(
                    text=fragment.text,
                    match_start=match.start(),
                    match_end=match.end(),
                )
                evidence_key = (
                    rule.rule_id,
                    fragment.fragment_id,
                    start_byte_offset,
                    end_byte_offset,
                )
                if evidence_key in evidence_keys:
                    continue
                evidence_keys.add(evidence_key)
                evidence.append(
                    ClassificationEvidence(
                        fragment_id=fragment.fragment_id,
                        rule_id=rule.rule_id,
                        start_byte_offset=start_byte_offset,
                        end_byte_offset=end_byte_offset,
                        excerpt=excerpt,
                    )
                )
    if not scores:
        return ClassificationResult(
            dce_document_id=document.dce_document_id,
            status="UNCLASSIFIED",
            classification=None,
            rule_match_count=0,
            evidence=(),
        )
    highest_score = max(scores.values())
    winners = sorted(
        classification for classification, score in scores.items() if score == highest_score
    )
    if len(winners) != 1:
        return ClassificationResult(
            dce_document_id=document.dce_document_id,
            status="REVIEW_REQUIRED",
            classification=None,
            rule_match_count=0,
            evidence=(),
        )
    classification = winners[0]
    return ClassificationResult(
        dce_document_id=document.dce_document_id,
        status="CLASSIFIED",
        classification=classification,
        rule_match_count=highest_score,
        evidence=tuple(evidence_by_classification[classification]),
    )


def _recording_command(
    *,
    dce_version_id: UUID,
    expected_dce_version_revision: int,
    projection: ClassificationProjection,
) -> RecordDceDocumentClassificationRunCommand:
    input_manifest_sha256 = classification_input_manifest_sha256(
        documents=projection.documents
    )
    classification_run_id = uuid5(
        dce_version_id,
        f"{input_manifest_sha256}:{CLASSIFIER_ID}:{CLASSIFIER_VERSION}",
    )
    return RecordDceDocumentClassificationRunCommand(
        command_id=classification_run_id,
        idempotency_key=classification_run_id,
        correlation_id=dce_version_id,
        classification_run_id=classification_run_id,
        dce_version_id=dce_version_id,
        expected_dce_version_revision=expected_dce_version_revision,
        input_manifest_sha256=input_manifest_sha256,
        classifier_id=CLASSIFIER_ID,
        classifier_version=CLASSIFIER_VERSION,
        status=projection.status,
        document_count=len(projection.documents),
        source_fragment_count=projection.source_fragment_count,
        source_char_count=projection.source_char_count,
        failure_code=projection.failure_code,
        results=[
            DceDocumentClassificationResultInput(
                dce_document_id=result.dce_document_id,
                status=result.status,
                classification=result.classification,
                rule_match_count=result.rule_match_count,
                evidence=[
                    DceDocumentClassificationEvidenceInput(
                        fragment_id=evidence.fragment_id,
                        rule_id=evidence.rule_id,
                        rule_version=CLASSIFIER_VERSION,
                        start_byte_offset=evidence.start_byte_offset,
                        end_byte_offset=evidence.end_byte_offset,
                        excerpt=evidence.excerpt,
                    )
                    for evidence in result.evidence
                ],
            )
            for result in projection.results
        ],
    )


def classification_input_manifest_sha256(
    *,
    documents: tuple[ClassificationDocument, ...],
) -> str:
    canonical_manifest = "\n".join(
        _manifest_lines(document=document) for document in documents
    )
    return sha256(canonical_manifest.encode("utf-8")).hexdigest()


def _manifest_lines(*, document: ClassificationDocument) -> str:
    if not document.fragments:
        return f"N|{document.dce_document_id}"
    return "\n".join(
        "|".join(
            (
                "D",
                str(document.dce_document_id),
                str(fragment.extraction_id),
                str(fragment.fragment_id),
                str(fragment.ordinal),
                fragment.text_sha256.lower(),
            )
        )
        for fragment in document.fragments
    )


def _bounded_excerpt(*, text: str, match_start: int, match_end: int) -> tuple[int, int, str]:
    start = max(0, match_start - 300)
    end = min(len(text), match_end + 700)
    while len(text[start:end].encode("utf-8")) > MAX_EXCERPT_CHARS:
        if end - match_end >= match_start - start and end > match_end:
            end -= 1
        elif start < match_start:
            start += 1
        else:
            break
    excerpt = text[start:end]
    return (
        len(text[:start].encode("utf-8")),
        len(text[:end].encode("utf-8")),
        excerpt,
    )

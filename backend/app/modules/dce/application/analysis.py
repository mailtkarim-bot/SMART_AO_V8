"""Deterministic, source-bound RC analysis over immutable DCE extraction fragments."""

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
    DceRcRequirementObservationInput,
    DceRcRequirementSourceInput,
    RecordDceRcAnalysisCommand,
)
from app.modules.dce.infrastructure.models.dce_extraction import (
    DceDocumentExtractionFragmentRecord,
    DceDocumentExtractionRecord,
)
from app.modules.dce.infrastructure.models.dce_version import (
    DceDocumentClassificationRecord,
    DceDocumentRecord,
    DceVersionRecord,
)
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, DispatchResult

ANALYZER_ID: Final = "smart-ao-rc-rules"
ANALYZER_VERSION: Final = "2"
SYSTEM_RC_ANALYSIS_ACTOR_ID: Final = UUID("00000000-0000-0000-0000-000000000014")
MAX_SOURCE_FRAGMENTS: Final = 100_000
MAX_SOURCE_CHARS: Final = 10_000_000
MAX_OBSERVATIONS: Final = 20_000
MAX_EXCERPT_CHARS: Final = 1_000

_REQUIRED_MARKERS: Final = ("obligatoire", "doit", "doivent", "exigé", "exigée", "impératif")
_OPTIONAL_MARKERS: Final = ("facultatif", "facultative", "peut", "possible", "sans obligation")


@dataclass(frozen=True, slots=True)
class RcAnalysisSourceFragment:
    """A trusted fragment selected from a completed immutable extraction."""

    dce_document_id: UUID
    extraction_id: UUID
    fragment_id: UUID
    ordinal: int
    text: str
    text_sha256: str
    document_family: str | None = None


@dataclass(frozen=True, slots=True)
class RcRequirementMatch:
    """One deterministic RC rule match with its exact source window."""

    requirement_kind: str
    rule_id: str
    directive: str
    fragment_id: UUID
    start_byte_offset: int
    end_byte_offset: int
    excerpt: str


@dataclass(frozen=True, slots=True)
class RcAnalysisProjection:
    """A terminal, bounded analysis projection ready for durable recording."""

    status: str
    failure_code: str | None
    source_fragment_count: int
    source_char_count: int
    source_fragments: tuple[RcAnalysisSourceFragment, ...]
    observations: tuple[RcRequirementMatch, ...]


@dataclass(frozen=True, slots=True)
class _RcRule:
    requirement_kind: str
    rule_id: str
    pattern: re.Pattern[str]
    document_families: frozenset[str] | None = None


_RC_RULES: Final = (
    _RcRule(
        "RC_DOCUMENT_CANDIDATURE",
        "CANDIDATURE_FORM_REFERENCE_V1",
        re.compile(r"\b(?:DC\s?[124]|e?DUME|dossier\s+de\s+candidature)\b", re.IGNORECASE),
    ),
    _RcRule(
        "RC_CONTENT_OFFER",
        "OFFER_TECHNICAL_MEMORY_V1",
        re.compile(r"\bmémoire\s+technique\b", re.IGNORECASE),
    ),
    _RcRule(
        "RC_CONTENT_OFFER",
        "OFFER_COMMITMENT_OR_PRICE_DOCUMENT_V1",
        re.compile(r"\b(?:acte\s+d['’]engagement|BPU|DPGF)\b", re.IGNORECASE),
    ),
    _RcRule(
        "RC_SUBMISSION_DEADLINE",
        "SUBMISSION_DEADLINE_V1",
        re.compile(
            r"\b(?:date\s+limite(?:\s+de)?\s+(?:remise|réception)|heure\s+limite|avant\s+le\s+\d)",
            re.IGNORECASE,
        ),
    ),
    _RcRule(
        "RC_RESPONSE_CHANNEL",
        "ELECTRONIC_SUBMISSION_CHANNEL_V1",
        re.compile(
            r"\b(?:profil\s+d['’]acheteur|dépôt\s+(?:électronique|dématérialisé)|plateforme\s+de\s+dépôt)\b",
            re.IGNORECASE,
        ),
    ),
    _RcRule(
        "RC_FILE_CONSTRAINT",
        "FILE_OR_SIGNATURE_CONSTRAINT_V1",
        re.compile(
            r"\b(?:taille\s+(?:maximale|maximum)|format\s+de\s+fichier|signature\s+électronique|format\s+PDF)\b",
            re.IGNORECASE,
        ),
    ),
    _RcRule(
        "RC_SITE_VISIT",
        "SITE_VISIT_V1",
        re.compile(
            r"\b(?:visite\s+(?:des\s+lieux|de\s+site|obligatoire|facultative)|rendez-vous\s+sur\s+site)\b",
            re.IGNORECASE,
        ),
    ),
    _RcRule(
        "RC_AWARD_CRITERION",
        "AWARD_CRITERION_OR_WEIGHTING_V1",
        re.compile(
            r"\b(?:critères?\s+(?:de\s+choix|d['’]attribution)|pondération|valeur\s+technique)\b",
            re.IGNORECASE,
        ),
    ),
    _RcRule(
        "RC_NEGOTIATION",
        "NEGOTIATION_V1",
        re.compile(r"\b(?:sans\s+négociation|négociation)\b", re.IGNORECASE),
    ),
    _RcRule(
        "RC_OFFER_VALIDITY",
        "OFFER_VALIDITY_V1",
        re.compile(r"\b(?:délai\s+de\s+validité|validité\s+de\s+l['’]offre)\b", re.IGNORECASE),
    ),
    _RcRule(
        "CCAP_PENALTIES",
        "CCAP_DELAY_PENALTIES_V1",
        re.compile(
            r"\b(?:pénalité(?:s)?\s+(?:de\s+retard|pour\s+retard)|pénalités?)\b",
            re.IGNORECASE,
        ),
        frozenset({"CCAP", "CCTP"}),
    ),
    _RcRule(
        "CCAP_RETENTION_GUARANTEE",
        "CCAP_RETENUE_GARANTIE_V1",
        re.compile(
            r"\b(?:retenue\s+de\s+garantie|retenue\s+pour\s+garantie)\b",
            re.IGNORECASE,
        ),
        frozenset({"CCAP", "CCTP"}),
    ),
    _RcRule(
        "CCAP_GUARANTEE",
        "CCAP_CAUTIONNEMENT_V1",
        re.compile(
            r"\b(?:cautionnement|garantie\s+à\s+première\s+demande|garantie\s+financière)\b",
            re.IGNORECASE,
        ),
        frozenset({"CCAP", "CCTP"}),
    ),
    _RcRule(
        "CCAP_INSURANCE",
        "CCAP_ASSURANCE_V1",
        re.compile(
            r"\b(?:assurance(?:s)?\s+(?:responsabilité|décennale|dommages)|attestation\s+d['’]assurance)\b",
            re.IGNORECASE,
        ),
        frozenset({"CCAP", "CCTP"}),
    ),
    _RcRule(
        "CCTP_VARIANTS",
        "CCTP_VARIANTES_OPTIONS_V1",
        re.compile(
            r"\b(?:variante(?:s)?|option(?:s)?|prestation\s+supplémentaire)\b",
            re.IGNORECASE,
        ),
        frozenset({"CCAP", "CCTP"}),
    ),
    _RcRule(
        "CCAP_SUBCONTRACTING",
        "CCAP_SOUS_TRAITANCE_V1",
        re.compile(r"\b(?:sous[- ]trait(?:ance|ant)|acte\s+spécial|DC4)\b", re.IGNORECASE),
        frozenset({"CCAP", "CCTP"}),
    ),
    _RcRule(
        "CCAP_QUALIFICATIONS",
        "CCAP_QUALIFICATIONS_V1",
        re.compile(
            r"\b(?:qualification(?:s)?\s+professionnelle|certification(?:s)?|qualibat|RGE|habilitation(?:s)?|agrément(?:s)?)\b",
            re.IGNORECASE,
        ),
        frozenset({"CCAP", "CCTP"}),
    ),
)


class DceRcAnalysisService:
    """Record a deterministic RC signal register without reading document originals."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        dispatcher: CommandDispatcher,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher

    def analyze(
        self,
        *,
        tenant_id: UUID,
        dce_version_id: UUID,
        now: datetime | None = None,
    ) -> DispatchResult:
        """Analyze all completed extraction fragments of one admitted, verified DCE."""

        effective_now = now or datetime.now(tz=UTC)
        sources = self._load_completed_fragments(
            tenant_id=tenant_id,
            dce_version_id=dce_version_id,
        )
        projection = _project_rc_requirements(sources=sources)
        command = _recording_command(
            dce_version_id=dce_version_id,
            projection=projection,
        )
        return self._dispatcher.dispatch(
            command=command,
            context=CommandContext(
                tenant_id=tenant_id,
                actor_id=SYSTEM_RC_ANALYSIS_ACTOR_ID,
                actor_kind="SYSTEM",
                received_at=effective_now,
            ),
        )

    def _load_completed_fragments(
        self,
        *,
        tenant_id: UUID,
        dce_version_id: UUID,
    ) -> tuple[RcAnalysisSourceFragment, ...]:
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
                raise ValueError("DCE_VERSION_NOT_ANALYSABLE")
            rows = session.execute(
                select(
                    DceDocumentRecord.id,
                    DceDocumentExtractionRecord.id,
                    DceDocumentExtractionFragmentRecord,
                    DceDocumentClassificationRecord.classification,
                )
                .join(
                    DceDocumentExtractionRecord,
                    and_(
                        DceDocumentExtractionRecord.tenant_id
                        == DceDocumentExtractionFragmentRecord.tenant_id,
                        DceDocumentExtractionRecord.id
                        == DceDocumentExtractionFragmentRecord.extraction_id,
                    ),
                )
                .join(
                    DceDocumentRecord,
                    and_(
                        DceDocumentRecord.tenant_id == DceDocumentExtractionRecord.tenant_id,
                        DceDocumentRecord.id == DceDocumentExtractionRecord.dce_document_id,
                    ),
                )
                .outerjoin(
                    DceDocumentClassificationRecord,
                    and_(
                        DceDocumentClassificationRecord.tenant_id == tenant_id,
                        DceDocumentClassificationRecord.dce_document_id == DceDocumentRecord.id,
                        DceDocumentClassificationRecord.is_current.is_(True),
                    ),
                )
                .where(
                    DceDocumentRecord.tenant_id == tenant_id,
                    DceDocumentRecord.dce_version_id == dce_version_id,
                    DceDocumentExtractionRecord.status == "COMPLETED",
                )
                .order_by(
                    DceDocumentRecord.id,
                    DceDocumentExtractionRecord.id,
                    DceDocumentExtractionFragmentRecord.ordinal,
                    DceDocumentExtractionFragmentRecord.id,
                )
            ).all()
            if not rows:
                raise ValueError("DCE_EXTRACTION_COMPLETED_REQUIRED")
            return tuple(
                RcAnalysisSourceFragment(
                    dce_document_id=document_id,
                    extraction_id=extraction_id,
                    fragment_id=fragment.id,
                    ordinal=fragment.ordinal,
                    text=fragment.text,
                    text_sha256=fragment.text_sha256,
                    document_family=classification,
                )
                for document_id, extraction_id, fragment, classification in rows
            )


def is_valid_rc_observation(
    *,
    requirement_kind: str,
    rule_id: str,
    directive: str,
    excerpt: str,
) -> bool:
    """Return whether a persisted observation is reproducible from its bounded excerpt."""

    for rule in _RC_RULES:
        if rule.requirement_kind != requirement_kind or rule.rule_id != rule_id:
            continue
        if rule.pattern.search(excerpt) is None:
            return False
        return _directive_from_excerpt(excerpt) == directive
    return False


def _project_rc_requirements(
    *,
    sources: tuple[RcAnalysisSourceFragment, ...],
) -> RcAnalysisProjection:
    source_char_count = sum(len(source.text) for source in sources)
    if len(sources) > MAX_SOURCE_FRAGMENTS or source_char_count > MAX_SOURCE_CHARS:
        return RcAnalysisProjection(
            status="REJECTED_LIMIT",
            failure_code="ANALYSIS_LIMIT",
            source_fragment_count=len(sources),
            source_char_count=source_char_count,
            source_fragments=sources,
            observations=(),
        )

    observations: list[RcRequirementMatch] = []
    for source in sources:
        for rule in _RC_RULES:
            if (
                rule.document_families is not None
                and source.document_family not in rule.document_families
            ):
                continue
            match = rule.pattern.search(source.text)
            if match is None:
                continue
            start_byte_offset, end_byte_offset, excerpt = _bounded_excerpt(
                text=source.text,
                match_start=match.start(),
                match_end=match.end(),
            )
            observations.append(
                RcRequirementMatch(
                    requirement_kind=rule.requirement_kind,
                    rule_id=rule.rule_id,
                    directive=_directive_from_excerpt(excerpt),
                    fragment_id=source.fragment_id,
                    start_byte_offset=start_byte_offset,
                    end_byte_offset=end_byte_offset,
                    excerpt=excerpt,
                )
            )
            if len(observations) > MAX_OBSERVATIONS:
                return RcAnalysisProjection(
                    status="REJECTED_LIMIT",
                    failure_code="ANALYSIS_LIMIT",
                    source_fragment_count=len(sources),
                    source_char_count=source_char_count,
                    source_fragments=sources,
                    observations=(),
                )

    if not observations:
        return RcAnalysisProjection(
            status="NO_RC_MARKER",
            failure_code="NO_RC_MARKER",
            source_fragment_count=len(sources),
            source_char_count=source_char_count,
            source_fragments=sources,
            observations=(),
        )
    return RcAnalysisProjection(
        status="COMPLETED",
        failure_code=None,
        source_fragment_count=len(sources),
        source_char_count=source_char_count,
        source_fragments=sources,
        observations=tuple(observations),
    )


def _recording_command(
    *,
    dce_version_id: UUID,
    projection: RcAnalysisProjection,
) -> RecordDceRcAnalysisCommand:
    input_manifest_sha256 = _input_manifest_sha256(sources=projection.source_fragments)
    analysis_identity = uuid5(
        dce_version_id,
        f"{input_manifest_sha256}:{ANALYZER_ID}:{ANALYZER_VERSION}",
    )
    source_order = {
        source.fragment_id: index for index, source in enumerate(projection.source_fragments)
    }
    observations = sorted(
        projection.observations,
        key=lambda observation: (
            source_order[observation.fragment_id],
            observation.start_byte_offset,
            observation.rule_id,
        ),
    )
    return RecordDceRcAnalysisCommand(
        command_id=analysis_identity,
        idempotency_key=analysis_identity,
        correlation_id=dce_version_id,
        analysis_id=analysis_identity,
        dce_version_id=dce_version_id,
        input_manifest_sha256=input_manifest_sha256,
        analyzer_id=ANALYZER_ID,
        analyzer_version=ANALYZER_VERSION,
        status=projection.status,
        source_fragment_count=projection.source_fragment_count,
        source_char_count=projection.source_char_count,
        failure_code=projection.failure_code,
        source_fragment_ids=[source.fragment_id for source in projection.source_fragments],
        observations=[
            DceRcRequirementObservationInput(
                observation_id=uuid5(
                    analysis_identity,
                    f"{index}:{observation.fragment_id}:{observation.rule_id}:"
                    f"{observation.start_byte_offset}:{observation.end_byte_offset}",
                ),
                requirement_kind=observation.requirement_kind,
                directive=observation.directive,
                rule_id=observation.rule_id,
                rule_version=ANALYZER_VERSION,
                excerpt=observation.excerpt,
                sources=[
                    DceRcRequirementSourceInput(
                        fragment_id=observation.fragment_id,
                        start_byte_offset=observation.start_byte_offset,
                        end_byte_offset=observation.end_byte_offset,
                    )
                ],
            )
            for index, observation in enumerate(observations, start=1)
        ],
    )


def _input_manifest_sha256(*, sources: tuple[RcAnalysisSourceFragment, ...]) -> str:
    canonical_manifest = "\n".join(
        "|".join(
            (
                str(source.dce_document_id),
                str(source.extraction_id),
                str(source.fragment_id),
                str(source.ordinal),
                source.text_sha256.lower(),
            )
        )
        for source in sources
    )
    return sha256(canonical_manifest.encode("utf-8")).hexdigest()


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


def _directive_from_excerpt(excerpt: str) -> str:
    normalized = excerpt.casefold()
    if any(marker in normalized for marker in _OPTIONAL_MARKERS):
        return "OPTIONAL_SIGNAL"
    if any(marker in normalized for marker in _REQUIRED_MARKERS):
        return "REQUIRED_SIGNAL"
    return "UNSPECIFIED"

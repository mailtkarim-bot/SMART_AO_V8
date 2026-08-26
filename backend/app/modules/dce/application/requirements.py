"""Deterministic materialization of atomic human-pending requirements from RC observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Final
from uuid import UUID, uuid5

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.dce.application.commands import (
    DceRequirementInput,
    RecordDceRequirementMaterializationRunCommand,
)
from app.modules.dce.infrastructure.models.dce_rc_analysis import (
    DceRcAnalysisRunRecord,
    DceRcRequirementObservationRecord,
    DceRcRequirementSourceRecord,
)
from app.modules.dce.infrastructure.models.dce_version import DceVersionRecord
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, DispatchResult

MATERIALIZER_ID: Final = "smart-ao-rc-requirement-materializer"
MATERIALIZER_VERSION: Final = "2"
SYSTEM_REQUIREMENTS_ACTOR_ID: Final = UUID("00000000-0000-0000-0000-000000000016")
MAX_OBSERVATIONS: Final = 20_000
_REQUIREMENT_TYPES: Final = {
    "RC_DOCUMENT_CANDIDATURE": "CANDIDATURE_DOCUMENT",
    "RC_CONTENT_OFFER": "OFFER_DOCUMENT",
    "RC_SUBMISSION_DEADLINE": "SUBMISSION_DEADLINE_SIGNAL",
    "RC_RESPONSE_CHANNEL": "SUBMISSION_CHANNEL",
    "RC_FILE_CONSTRAINT": "FILE_CONSTRAINT",
    "RC_SITE_VISIT": "SITE_VISIT",
    "RC_AWARD_CRITERION": "AWARD_CRITERION_SIGNAL",
    "RC_NEGOTIATION": "NEGOTIATION_SIGNAL",
    "RC_OFFER_VALIDITY": "OFFER_VALIDITY_SIGNAL",
    "CCAP_PENALTIES": "CONTRACT_RISK_SIGNAL",
    "CCAP_RETENTION_GUARANTEE": "CONTRACT_RISK_SIGNAL",
    "CCAP_GUARANTEE": "CONTRACT_RISK_SIGNAL",
    "CCAP_INSURANCE": "CONTRACT_RISK_SIGNAL",
    "CCTP_VARIANTS": "CONTRACT_RISK_SIGNAL",
    "CCAP_SUBCONTRACTING": "CONTRACT_RISK_SIGNAL",
    "CCAP_QUALIFICATIONS": "CONTRACT_RISK_SIGNAL",
}


@dataclass(frozen=True, slots=True)
class RequirementSignal:
    observation_id: UUID
    requirement_kind: str
    directive: str
    rule_id: str
    rule_version: str
    fragment_id: UUID
    start_byte_offset: int
    end_byte_offset: int


@dataclass(frozen=True, slots=True)
class RequirementProjection:
    status: str
    failure_code: str | None
    signals: tuple[RequirementSignal, ...]


class DceRequirementsService:
    def __init__(
        self, *, session_factory: sessionmaker[Session], dispatcher: CommandDispatcher
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher

    def materialize(
        self,
        *,
        tenant_id: UUID,
        dce_version_id: UUID,
        dce_rc_analysis_id: UUID,
        now: datetime | None = None,
    ) -> DispatchResult:
        effective_now = now or datetime.now(tz=UTC)
        dce_rc_analysis_id = UUID(str(dce_rc_analysis_id))
        signals = self._load_signals(
            tenant_id=tenant_id,
            dce_version_id=dce_version_id,
            dce_rc_analysis_id=dce_rc_analysis_id,
        )
        projection = project_requirements(signals=signals)
        command = recording_command(
            dce_version_id=dce_version_id,
            dce_rc_analysis_id=dce_rc_analysis_id,
            projection=projection,
        )
        return self._dispatcher.dispatch(
            command=command,
            context=CommandContext(
                tenant_id=tenant_id,
                actor_id=SYSTEM_REQUIREMENTS_ACTOR_ID,
                actor_kind="SYSTEM",
                received_at=effective_now,
            ),
        )

    def _load_signals(
        self, *, tenant_id: UUID, dce_version_id: UUID, dce_rc_analysis_id: UUID
    ) -> tuple[RequirementSignal, ...]:
        with self._session_factory() as session:
            version = session.scalar(
                select(DceVersionRecord).where(
                    DceVersionRecord.tenant_id == tenant_id, DceVersionRecord.id == dce_version_id
                )
            )
            analysis = session.scalar(
                select(DceRcAnalysisRunRecord).where(
                    DceRcAnalysisRunRecord.tenant_id == tenant_id,
                    DceRcAnalysisRunRecord.id == dce_rc_analysis_id,
                )
            )
            if (
                version is None
                or version.lifecycle not in {"ADMITTED", "SUPERSEDED"}
                or version.integrity != "VERIFIED"
            ):
                raise ValueError("DCE_VERSION_NOT_REQUIREMENTS_READY")
            if (
                analysis is None
                or analysis.dce_version_id != dce_version_id
                or analysis.status != "COMPLETED"
            ):
                raise ValueError("DCE_RC_ANALYSIS_COMPLETED_REQUIRED")
            rows = session.execute(
                select(DceRcRequirementObservationRecord, DceRcRequirementSourceRecord)
                .join(
                    DceRcRequirementSourceRecord,
                    and_(
                        DceRcRequirementSourceRecord.tenant_id
                        == DceRcRequirementObservationRecord.tenant_id,
                        DceRcRequirementSourceRecord.observation_id
                        == DceRcRequirementObservationRecord.id,
                    ),
                )
                .where(
                    DceRcRequirementObservationRecord.tenant_id == tenant_id,
                    DceRcRequirementObservationRecord.analysis_id == dce_rc_analysis_id,
                )
                .order_by(DceRcRequirementObservationRecord.id)
            ).all()
            return tuple(
                RequirementSignal(
                    observation_id=observation.id,
                    requirement_kind=observation.requirement_kind,
                    directive=observation.directive,
                    rule_id=observation.rule_id,
                    rule_version=observation.rule_version,
                    fragment_id=source.fragment_id,
                    start_byte_offset=source.start_byte_offset,
                    end_byte_offset=source.end_byte_offset,
                )
                for observation, source in rows
            )


def project_requirements(*, signals: tuple[RequirementSignal, ...]) -> RequirementProjection:
    if len(signals) > MAX_OBSERVATIONS:
        return RequirementProjection(
            status="REJECTED_LIMIT", failure_code="REQUIREMENT_LIMIT", signals=signals
        )
    if not signals:
        return RequirementProjection(status="NO_SIGNAL", failure_code=None, signals=())
    if any(signal.requirement_kind not in _REQUIREMENT_TYPES for signal in signals):
        return RequirementProjection(
            status="FAILED_SAFE", failure_code="REQUIREMENT_MAPPING_UNKNOWN", signals=signals
        )
    return RequirementProjection(status="COMPLETED", failure_code=None, signals=signals)


def requirements_manifest_sha256(*, signals: tuple[RequirementSignal, ...]) -> str:
    payload = "\n".join(
        "|".join(
            (
                str(signal.observation_id),
                signal.requirement_kind,
                signal.directive,
                signal.rule_id,
                signal.rule_version,
                str(signal.fragment_id),
                str(signal.start_byte_offset),
                str(signal.end_byte_offset),
            )
        )
        for signal in signals
    )
    return sha256(payload.encode()).hexdigest()


def recording_command(
    *, dce_version_id: UUID, dce_rc_analysis_id: UUID, projection: RequirementProjection
) -> RecordDceRequirementMaterializationRunCommand:
    manifest = requirements_manifest_sha256(signals=projection.signals)
    run_id = uuid5(dce_rc_analysis_id, f"{manifest}:{MATERIALIZER_ID}:{MATERIALIZER_VERSION}")
    return RecordDceRequirementMaterializationRunCommand(
        command_id=run_id,
        idempotency_key=run_id,
        correlation_id=dce_version_id,
        requirements_run_id=run_id,
        dce_version_id=dce_version_id,
        dce_rc_analysis_id=dce_rc_analysis_id,
        input_manifest_sha256=manifest,
        materializer_id=MATERIALIZER_ID,
        materializer_version=MATERIALIZER_VERSION,
        status=projection.status,
        source_observation_count=len(projection.signals),
        failure_code=projection.failure_code,
        requirements=[
            DceRequirementInput(
                requirement_id=uuid5(run_id, str(signal.observation_id)),
                source_observation_id=signal.observation_id,
                requirement_type=_REQUIREMENT_TYPES[signal.requirement_kind],
                directive_signal=signal.directive,
                confirmation_status="PENDING_HUMAN_CONFIRMATION",
                uncertainty_status="SOURCE_SIGNAL_ONLY",
            )
            for signal in projection.signals
        ]
        if projection.status == "COMPLETED"
        else [],
    )

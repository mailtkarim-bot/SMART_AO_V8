"""Deterministic, conservative impact preparation for Case-scoped DCE rectifications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.commands import (
    CaseDceImpactItemInput,
    RecordCaseDceImpactRunCommand,
)
from app.modules.dce.infrastructure.models.dce_requirements import (
    DceRequirementMaterializationRunRecord,
    DceRequirementRecord,
)
from app.modules.dce.infrastructure.models.dce_version import DceVersionRecord
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, DispatchResult

IMPACT_ALGORITHM_ID = "smart-ao-case-dce-impact"
IMPACT_ALGORITHM_VERSION = "1"
SYSTEM_IMPACT_ACTOR_ID = UUID("00000000-0000-0000-0000-000000000017")


@dataclass(frozen=True, slots=True)
class ImpactRequirement:
    id: UUID
    requirement_type: str
    directive_signal: str
    source_observation_id: UUID


def load_impact_requirements(
    *,
    session: Session,
    tenant_id: UUID,
    dce_version_id: UUID,
) -> tuple[ImpactRequirement, ...]:
    """Load requirements from the newest safe terminal materialization for one DCE."""

    run = session.scalar(
        sa.select(DceRequirementMaterializationRunRecord)
        .where(
            DceRequirementMaterializationRunRecord.tenant_id == tenant_id,
            DceRequirementMaterializationRunRecord.dce_version_id == dce_version_id,
            DceRequirementMaterializationRunRecord.status.in_(("COMPLETED", "NO_SIGNAL")),
        )
        .order_by(
            DceRequirementMaterializationRunRecord.created_at.desc(),
            DceRequirementMaterializationRunRecord.id.desc(),
        )
    )
    if run is None:
        raise ValueError("DCE_REQUIREMENTS_NOT_READY")
    requirements = session.scalars(
        sa.select(DceRequirementRecord)
        .where(
            DceRequirementRecord.tenant_id == tenant_id,
            DceRequirementRecord.requirements_run_id == run.id,
        )
        .order_by(DceRequirementRecord.id)
    )
    return tuple(
        ImpactRequirement(
            id=requirement.id,
            requirement_type=requirement.requirement_type,
            directive_signal=requirement.directive_signal,
            source_observation_id=requirement.source_observation_id,
        )
        for requirement in requirements
    )


def impact_manifest_sha256(
    *,
    case_id: UUID,
    predecessor_dce_version_id: UUID,
    successor_dce_version_id: UUID,
    previous_requirements: tuple[ImpactRequirement, ...],
    successor_requirements: tuple[ImpactRequirement, ...],
) -> str:
    lines = [
        f"CASE|{case_id}",
        f"PREDECESSOR|{predecessor_dce_version_id}",
        f"SUCCESSOR|{successor_dce_version_id}",
    ]
    lines.extend(
        f"PREVIOUS|{item.id}|{item.requirement_type}|{item.directive_signal}|"
        f"{item.source_observation_id}"
        for item in previous_requirements
    )
    lines.extend(
        f"SUCCESSOR|{item.id}|{item.requirement_type}|{item.directive_signal}|"
        f"{item.source_observation_id}"
        for item in successor_requirements
    )
    return sha256("\n".join(lines).encode("ascii")).hexdigest()


def expected_impact_items(
    *,
    impact_run_id: UUID,
    previous_requirements: tuple[ImpactRequirement, ...],
    successor_requirements: tuple[ImpactRequirement, ...],
) -> tuple[CaseDceImpactItemInput, ...]:
    items: list[CaseDceImpactItemInput] = [
        CaseDceImpactItemInput(
            impact_item_id=uuid5(impact_run_id, "DCE_VERSION_REPLACED"),
            impact_kind="DCE_VERSION_REPLACED",
            review_state="REVIEW_REQUIRED",
            evidence_code="RECTIFICATION_CHAIN",
        )
    ]
    items.extend(
        CaseDceImpactItemInput(
            impact_item_id=uuid5(impact_run_id, f"PREVIOUS_REQUIREMENT:{requirement.id}"),
            impact_kind="PREVIOUS_REQUIREMENT_REQUIRES_REVIEW",
            previous_requirement_id=requirement.id,
            review_state="REVIEW_REQUIRED",
            evidence_code="PREVIOUS_REQUIREMENT",
        )
        for requirement in previous_requirements
    )
    items.extend(
        CaseDceImpactItemInput(
            impact_item_id=uuid5(impact_run_id, f"SUCCESSOR_REQUIREMENT:{requirement.id}"),
            impact_kind="SUCCESSOR_REQUIREMENT_CANDIDATE",
            successor_requirement_id=requirement.id,
            review_state="PENDING_HUMAN_REVIEW",
            evidence_code="SUCCESSOR_REQUIREMENT",
        )
        for requirement in successor_requirements
    )
    if not previous_requirements and not successor_requirements:
        items.append(
            CaseDceImpactItemInput(
                impact_item_id=uuid5(impact_run_id, "VERSION_HAS_NO_MATERIALIZED_SIGNAL"),
                impact_kind="VERSION_HAS_NO_MATERIALIZED_SIGNAL",
                review_state="REVIEW_REQUIRED",
                evidence_code="NO_SIGNAL",
            )
        )
    return tuple(items)


class CaseDceImpactService:
    """Prepare and dispatch one conservative impact run for a Case rectification."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        dispatcher: CommandDispatcher,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher

    def run(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        predecessor_dce_version_id: UUID,
        successor_dce_version_id: UUID,
        now: datetime | None = None,
    ) -> DispatchResult:
        with self._session_factory() as session:
            case = session.scalar(
                sa.select(CaseRecord).where(
                    CaseRecord.tenant_id == tenant_id,
                    CaseRecord.id == case_id,
                )
            )
            predecessor = session.scalar(
                sa.select(DceVersionRecord).where(
                    DceVersionRecord.tenant_id == tenant_id,
                    DceVersionRecord.id == predecessor_dce_version_id,
                )
            )
            successor = session.scalar(
                sa.select(DceVersionRecord).where(
                    DceVersionRecord.tenant_id == tenant_id,
                    DceVersionRecord.id == successor_dce_version_id,
                )
            )
            if case is None or case.lifecycle == "ARCHIVED":
                raise ValueError("CASE_NOT_FOUND_OR_FORBIDDEN")
            if (
                predecessor is None
                or successor is None
                or case.applicable_dce_version_id != predecessor.id
                or predecessor.consultation_id != successor.consultation_id
                or successor.predecessor_dce_version_id != predecessor.id
                or predecessor.integrity != "VERIFIED"
                or successor.lifecycle != "ADMITTED"
                or successor.integrity != "VERIFIED"
            ):
                raise ValueError("CASE_DCE_PREDECESSOR_MISMATCH")
            previous_requirements = load_impact_requirements(
                session=session,
                tenant_id=tenant_id,
                dce_version_id=predecessor.id,
            )
            successor_requirements = load_impact_requirements(
                session=session,
                tenant_id=tenant_id,
                dce_version_id=successor.id,
            )

        manifest = impact_manifest_sha256(
            case_id=case_id,
            predecessor_dce_version_id=predecessor_dce_version_id,
            successor_dce_version_id=successor_dce_version_id,
            previous_requirements=previous_requirements,
            successor_requirements=successor_requirements,
        )
        impact_run_id = uuid5(
            case_id,
            f"{predecessor_dce_version_id}:{successor_dce_version_id}:"
            f"{manifest}:{IMPACT_ALGORITHM_ID}:{IMPACT_ALGORITHM_VERSION}",
        )
        items = expected_impact_items(
            impact_run_id=impact_run_id,
            previous_requirements=previous_requirements,
            successor_requirements=successor_requirements,
        )
        command = RecordCaseDceImpactRunCommand(
            command_id=impact_run_id,
            idempotency_key=impact_run_id,
            correlation_id=successor_dce_version_id,
            impact_run_id=impact_run_id,
            case_id=case_id,
            predecessor_dce_version_id=predecessor_dce_version_id,
            successor_dce_version_id=successor_dce_version_id,
            input_manifest_sha256=manifest,
            algorithm_id=IMPACT_ALGORITHM_ID,
            algorithm_version=IMPACT_ALGORITHM_VERSION,
            status="NO_SIGNAL"
            if not previous_requirements and not successor_requirements
            else "COMPLETED",
            previous_requirement_count=len(previous_requirements),
            successor_requirement_count=len(successor_requirements),
            items=list(items),
        )
        return self._dispatcher.dispatch(
            command=command,
            context=CommandContext(
                tenant_id=tenant_id,
                actor_id=SYSTEM_IMPACT_ACTOR_ID,
                actor_kind="SYSTEM",
                received_at=now or datetime.now(tz=UTC),
            ),
        )

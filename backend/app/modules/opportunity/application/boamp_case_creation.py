from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.case.application.commands import CreateCaseCommand
from app.modules.opportunity.infrastructure.observation_models import (
    BoampOpportunityObservationRecord,
    BoampOpportunityQualificationRecord,
)
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, DispatchResult


@dataclass(frozen=True, slots=True)
class BoampCaseCreationCommand:
    observation_id: UUID
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None


class BoampCaseCreationService:
    """Turns a human-qualified public signal into one normal Case command."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        dispatcher: CommandDispatcher,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher

    def create(
        self,
        *,
        context: CommandContext,
        command: BoampCaseCreationCommand,
        now: datetime,
    ) -> DispatchResult:
        if context.actor_kind != "PATRON_ADMIN":
            raise PermissionError("BOAMP_CASE_CREATION_PATRON_REQUIRED")
        with self._session_factory() as session:
            observation = session.scalar(
                sa.select(BoampOpportunityObservationRecord).where(
                    BoampOpportunityObservationRecord.tenant_id == context.tenant_id,
                    BoampOpportunityObservationRecord.id == command.observation_id,
                )
            )
            qualification = session.scalar(
                sa.select(BoampOpportunityQualificationRecord)
                .where(
                    BoampOpportunityQualificationRecord.tenant_id == context.tenant_id,
                    BoampOpportunityQualificationRecord.observation_id == command.observation_id,
                    BoampOpportunityQualificationRecord.decision == "QUALIFIED",
                )
                .order_by(BoampOpportunityQualificationRecord.created_at.desc())
            )
        if observation is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        if qualification is None:
            raise ValueError("BOAMP_QUALIFICATION_REQUIRED")

        case_id = uuid5(NAMESPACE_URL, f"smart-ao:case:{command.idempotency_key}")
        title = (observation.title or f"Avis BOAMP {observation.source_notice_id}").strip()[:240]
        description = _description(observation)
        origin_rationale = (
            f"Signal BOAMP {observation.source_notice_id} qualifié par décision humaine; "
            f"score public figé {observation.score}/100 ({observation.score_version})."
        )[:2_000]
        return self._dispatcher.dispatch(
            command=CreateCaseCommand(
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
                case_id=case_id,
                title=title,
                object_description=description,
                scope_kind="CUSTOM",
                scope_justification=(
                    "Périmètre issu d’un signal public : confirmer les lots et pièces du DCE "
                    "avant chiffrage ou décision."
                ),
                origin_kind="OPPORTUNITY",
                origin_rationale=origin_rationale,
                origin_reference_id=observation.id,
            ),
            context=context,
        )


def _description(observation: BoampOpportunityObservationRecord) -> str:
    departments = ", ".join(observation.department_codes) or "non précisés"
    market_types = ", ".join(observation.market_types) or "non précisés"
    deadline = (
        observation.response_deadline.isoformat()
        if observation.response_deadline
        else "non précisée"
    )
    return (
        f"Observation publique BOAMP {observation.source_notice_id}. "
        f"Départements : {departments}. Types de marché : {market_types}. "
        f"Date limite publiée : {deadline}. "
        "Description contractuelle à compléter après réception et contrôle du DCE."
    )[:10_000]

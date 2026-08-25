"""Patronal reading and human qualification of persisted BOAMP observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.opportunity.infrastructure.boamp_qualification_repository import (
    BoampQualificationRepository,
    QualificationPersistenceResult,
)
from app.modules.opportunity.infrastructure.observation_models import (
    BoampOpportunityObservationRecord,
)
from app.platform.events.dispatcher import CommandContext
from app.platform.security.context import ActorKind
from app.platform.security.models import TenantMembershipRecord


class QualificationDecision(StrEnum):
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"
    SNOOZED = "SNOOZED"


class QualificationReason(StrEnum):
    RELEVANT_PUBLIC_SIGNAL = "RELEVANT_PUBLIC_SIGNAL"
    NOT_RELEVANT = "NOT_RELEVANT"
    INSUFFICIENT_PUBLIC_DATA = "INSUFFICIENT_PUBLIC_DATA"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class BoampQualificationCommand:
    observation_id: UUID
    decision: QualificationDecision
    reason_code: QualificationReason
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None

    def validate(self) -> None:
        allowed = {
            QualificationDecision.QUALIFIED: {QualificationReason.RELEVANT_PUBLIC_SIGNAL},
            QualificationDecision.REJECTED: {
                QualificationReason.NOT_RELEVANT,
                QualificationReason.EXPIRED,
            },
            QualificationDecision.SNOOZED: {QualificationReason.INSUFFICIENT_PUBLIC_DATA},
        }
        if self.reason_code not in allowed[self.decision]:
            raise ValueError("qualification decision and reason are incompatible")


@dataclass(frozen=True, slots=True)
class PatronBoampObservationProjection:
    observation_id: UUID
    source_notice_id: str
    title: str | None
    publication_date: str | None
    response_deadline: str | None
    department_codes: tuple[str, ...]
    market_types: tuple[str, ...]
    source_status: str | None
    score_version: str
    score: int
    score_explanation: dict[str, object]
    fingerprint_sha256: str


class PatronBoampObservationService:
    def __init__(self, *, repository: BoampQualificationRepository) -> None:
        self._repository = repository

    def read(
        self,
        *,
        session: Session,
        tenant_id: UUID,
        actor_id: UUID,
        actor_kind: str,
        limit: int = 50,
        min_score: int = 0,
    ) -> tuple[PatronBoampObservationProjection, ...]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        if not 0 <= min_score <= 100:
            raise ValueError("min_score must be between 0 and 100")
        self._require_patron_membership(
            session=session, tenant_id=tenant_id, actor_id=actor_id, actor_kind=actor_kind
        )
        records = self._repository.list_observations(
            session=session, tenant_id=tenant_id, limit=limit, min_score=min_score
        )
        return tuple(_projection(record) for record in records)

    def qualify(
        self,
        *,
        session: Session,
        context: CommandContext,
        command: BoampQualificationCommand,
        now: datetime,
    ) -> QualificationPersistenceResult:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value:
            raise PermissionError("BOAMP_QUALIFICATION_PATRON_REQUIRED")
        command.validate()
        self._require_patron_membership(
            session=session,
            tenant_id=context.tenant_id,
            actor_id=context.actor_id,
            actor_kind=context.actor_kind,
        )
        observation = session.scalar(
            sa.select(BoampOpportunityObservationRecord).where(
                BoampOpportunityObservationRecord.tenant_id == context.tenant_id,
                BoampOpportunityObservationRecord.id == command.observation_id,
            )
        )
        if observation is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        return self._repository.persist_qualification(
            session=session,
            tenant_id=context.tenant_id,
            actor_id=context.actor_id,
            observation=observation,
            command=command,
            now=now,
        )

    @staticmethod
    def _require_patron_membership(
        *, session: Session, tenant_id: UUID, actor_id: UUID, actor_kind: str
    ) -> None:
        if actor_kind != ActorKind.PATRON_ADMIN.value:
            raise PermissionError("BOAMP_QUALIFICATION_PATRON_REQUIRED")
        member = session.scalar(
            sa.select(TenantMembershipRecord.id).where(
                TenantMembershipRecord.tenant_id == tenant_id,
                TenantMembershipRecord.identity_id == actor_id,
                TenantMembershipRecord.role == ActorKind.PATRON_ADMIN.value,
                TenantMembershipRecord.state == "ACTIVE",
            )
        )
        if member is None:
            raise PermissionError("BOAMP_QUALIFICATION_PATRON_REQUIRED")


def _projection(record: BoampOpportunityObservationRecord) -> PatronBoampObservationProjection:
    return PatronBoampObservationProjection(
        observation_id=record.id,
        source_notice_id=record.source_notice_id,
        title=record.title,
        publication_date=record.publication_date.isoformat()
        if record.publication_date is not None
        else None,
        response_deadline=record.response_deadline.isoformat()
        if record.response_deadline is not None
        else None,
        department_codes=tuple(record.department_codes),
        market_types=tuple(record.market_types),
        source_status=record.source_status,
        score_version=record.score_version,
        score=record.score,
        score_explanation=dict(record.score_explanation_json),
        fingerprint_sha256=record.fingerprint_sha256,
    )

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.modules.opportunity.application.boamp_qualification import (
    BoampQualificationCommand,
    PatronBoampObservationService,
    QualificationDecision,
    QualificationReason,
)
from app.modules.opportunity.infrastructure.boamp_observation_repository import (
    BoampObservationRepository,
    ingestion_request_hash,
)
from app.modules.opportunity.infrastructure.boamp_qualification_repository import (
    BoampQualificationRepository,
)
from app.modules.opportunity.infrastructure.observation_models import (
    BoampOpportunityQualificationRecord,
)
from app.platform.events.dispatcher import CommandContext
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord
from app.platform.security.context import ActorKind
from sqlalchemy.orm import Session, sessionmaker
from tests.infrastructure.test_boamp_observation_persistence import _scored, _seed

pytestmark = pytest.mark.db
NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


def _persist_observation(session_factory: sessionmaker[Session]):
    tenant_id, actor_id, profile_id = _seed(session_factory)
    scored = _scored()
    with session_factory.begin() as session:
        result = BoampObservationRepository().persist(
            session=session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            profile_id=profile_id,
            profile_version=1,
            command_id=uuid4(),
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            request_hash=ingestion_request_hash(
                profile_id=profile_id,
                profile_version=1,
                pages_read=1,
                truncated=False,
                scored_candidates=scored,
            ),
            started_at=NOW,
            completed_at=NOW,
            pages_read=1,
            truncated=False,
            scored_candidates=scored,
        )
    return tenant_id, actor_id, result.observation_ids[0]


def _command(observation_id):
    return BoampQualificationCommand(
        observation_id=observation_id,
        decision=QualificationDecision.QUALIFIED,
        reason_code=QualificationReason.RELEVANT_PUBLIC_SIGNAL,
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
    )


def test_qualification_is_atomic_idempotent_and_append_only(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, actor_id, observation_id = _persist_observation(session_factory)
    command = _command(observation_id)
    context = CommandContext(
        tenant_id=tenant_id,
        actor_id=actor_id,
        actor_kind=ActorKind.PATRON_ADMIN.value,
        received_at=NOW,
        correlation_id=command.correlation_id,
    )
    service = PatronBoampObservationService(repository=BoampQualificationRepository())

    with session_factory.begin() as session:
        first = service.qualify(session=session, context=context, command=command, now=NOW)
    with session_factory.begin() as session:
        replay = service.qualify(session=session, context=context, command=command, now=NOW)

    assert first.replayed is False
    assert replay.replayed is True
    assert replay.qualification_id == first.qualification_id
    assert replay.event_id == first.event_id

    with session_factory() as session:
        assert session.scalar(
            sa.select(sa.func.count(BoampOpportunityQualificationRecord.id))
        ) == 1
        assert session.scalar(
            sa.select(sa.func.count(DomainEventRecord.id)).where(
                DomainEventRecord.event_type == "BoampOpportunityQualified"
            )
        ) == 1
        assert session.scalar(
            sa.select(sa.func.count(OutboxMessageRecord.id)).where(
                OutboxMessageRecord.topic == "opportunity.boamp.qualification.recorded"
            )
        ) == 1
    with pytest.raises(sa.exc.DBAPIError), session_factory.begin() as session:
        session.execute(
            sa.text(
                "UPDATE boamp_opportunity_qualifications "
                "SET decision = 'REJECTED' WHERE id = :qualification_id"
            ),
            {"qualification_id": first.qualification_id},
        )

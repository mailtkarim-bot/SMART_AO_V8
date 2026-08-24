from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.modules.opportunity.application.boamp_ingestion import OpportunityCandidate
from app.modules.opportunity.application.boamp_scoring import (
    BoampOpportunityScoringService,
)
from app.modules.opportunity.domain.watch_profile import WatchProfileCriteria
from app.modules.opportunity.infrastructure.boamp_observation_repository import (
    BoampObservationPersistenceConflict,
    BoampObservationRepository,
    ingestion_request_hash,
)
from app.modules.opportunity.infrastructure.models import (
    OpportunityWatchProfileRecord,
    OpportunityWatchProfileVersionRecord,
)
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord, TenantRecord
from app.platform.security.models import IdentityRecord, TenantMembershipRecord
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.db
NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


def _candidate() -> OpportunityCandidate:
    return OpportunityCandidate(
        source="BOAMP",
        source_notice_id="A-1",
        title="Réhabilitation école",
        publication_date=date(2026, 8, 20),
        response_deadline=NOW + timedelta(days=5),
        department_codes=("59",),
        market_types=("TRAVAUX",),
        source_status="EN_COURS",
    )


def _scored() -> tuple[tuple[OpportunityCandidate, object], ...]:
    candidate = _candidate()
    score = BoampOpportunityScoringService().score(
        candidate=candidate,
        criteria=WatchProfileCriteria(
            keywords=("réhabilitation",), included_departments=("59",)
        ),
        now=NOW,
    )
    return ((candidate, score),)


def _seed(session_factory: sessionmaker[Session]):
    tenant_id, actor_id, profile_id = uuid4(), uuid4(), uuid4()
    membership_id, version_id = uuid4(), uuid4()
    with session_factory.begin() as session:
        session.add(
            TenantRecord(id=tenant_id, slug=f"tenant-{tenant_id.hex[:12]}", lifecycle="ACTIVE")
        )
        session.flush()
        session.add(
            IdentityRecord(
                id=actor_id,
                email_normalized=f"actor-{actor_id.hex[:12]}@example.test",
                lifecycle="ACTIVE",
                email_verified_at=NOW,
            )
        )
        session.add(
            TenantMembershipRecord(
                id=membership_id,
                tenant_id=tenant_id,
                identity_id=actor_id,
                role="PATRON_ADMIN",
                state="ACTIVE",
                activated_at=NOW,
                revoked_at=None,
            )
        )
        session.add(
            OpportunityWatchProfileRecord(
                id=profile_id,
                tenant_id=tenant_id,
                aggregate_revision=0,
                name="Veille BTP",
                state="ACTIVE",
                current_version=1,
                actor_id=actor_id,
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
            )
        )
        session.add(
            OpportunityWatchProfileVersionRecord(
                id=version_id,
                tenant_id=tenant_id,
                profile_id=profile_id,
                version_number=1,
                name="Veille BTP",
                criteria_json=WatchProfileCriteria(keywords=("réhabilitation",)).snapshot(),
                criteria_sha256="a" * 64,
                actor_id=actor_id,
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
            )
        )
    return tenant_id, actor_id, profile_id


def test_repository_persists_and_replays_with_audit(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, actor_id, profile_id = _seed(session_factory)
    scored = _scored()
    request_hash = ingestion_request_hash(
        profile_id=profile_id,
        profile_version=1,
        pages_read=1,
        truncated=False,
        scored_candidates=scored,
    )
    command_id, idempotency_key = uuid4(), uuid4()
    repository = BoampObservationRepository()
    with session_factory.begin() as session:
        first = repository.persist(
            session=session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            profile_id=profile_id,
            profile_version=1,
            command_id=command_id,
            idempotency_key=idempotency_key,
            correlation_id=uuid4(),
            request_hash=request_hash,
            started_at=NOW,
            completed_at=NOW,
            pages_read=1,
            truncated=False,
            scored_candidates=scored,
        )
    with session_factory.begin() as session:
        replay = repository.persist(
            session=session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            profile_id=profile_id,
            profile_version=1,
            command_id=command_id,
            idempotency_key=idempotency_key,
            correlation_id=uuid4(),
            request_hash=request_hash,
            started_at=NOW,
            completed_at=NOW,
            pages_read=1,
            truncated=False,
            scored_candidates=scored,
        )
    assert first.replayed is False
    assert replay.replayed is True
    assert replay.run_id == first.run_id
    with session_factory() as session:
        assert session.scalar(sa.select(sa.func.count(DomainEventRecord.id))) == 1
        assert session.scalar(sa.select(sa.func.count(OutboxMessageRecord.id))) == 1


def test_repository_rejects_same_idempotency_with_different_hash(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, actor_id, profile_id = _seed(session_factory)
    scored = _scored()
    repository = BoampObservationRepository()
    command_id, idempotency_key = uuid4(), uuid4()
    with session_factory.begin() as session:
        repository.persist(
            session=session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            profile_id=profile_id,
            profile_version=1,
            command_id=command_id,
            idempotency_key=idempotency_key,
            correlation_id=None,
            request_hash="a" * 64,
            started_at=NOW,
            completed_at=NOW,
            pages_read=1,
            truncated=False,
            scored_candidates=scored,
        )
    with pytest.raises(BoampObservationPersistenceConflict), session_factory.begin() as session:
        repository.persist(
            session=session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            profile_id=profile_id,
            profile_version=1,
            command_id=command_id,
            idempotency_key=idempotency_key,
            correlation_id=None,
            request_hash="b" * 64,
            started_at=NOW,
            completed_at=NOW,
            pages_read=1,
            truncated=False,
            scored_candidates=scored,
        )

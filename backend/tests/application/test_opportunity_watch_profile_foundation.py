from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.opportunity.application.patron_watch_profile import (
    PatronWatchProfileService,
    opportunity_watch_profile_handlers,
)
from app.modules.opportunity.application.watch_profile_commands import (
    AddOpportunityWatchProfileVersionCommand,
    CreateOpportunityWatchProfileCommand,
)
from app.modules.opportunity.infrastructure.models import (
    OpportunityWatchProfileRecord,
    OpportunityWatchProfileVersionRecord,
)
from app.platform.events.dispatcher import CommandDispatcher, CommandExecutionError
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord, TenantRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import capabilities_for
from app.platform.security.context import ActorContext, ActorKind, MembershipState
from app.platform.security.models import IdentityRecord, TenantMembershipRecord
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.db
NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def isolate_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_actor(session_factory: sessionmaker[Session]) -> ActorContext:
    tenant_id = uuid4()
    identity_id = uuid4()
    membership_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            TenantRecord(id=tenant_id, slug=f"tenant-{tenant_id.hex[:12]}", lifecycle="ACTIVE")
        )
        session.add(
            IdentityRecord(
                id=identity_id,
                email_normalized=f"actor-{identity_id.hex[:12]}@example.test",
                lifecycle="ACTIVE",
                email_verified_at=NOW,
            )
        )
        session.add(
            TenantMembershipRecord(
                id=membership_id,
                tenant_id=tenant_id,
                identity_id=identity_id,
                role="PATRON_ADMIN",
                state="ACTIVE",
                activated_at=NOW,
                revoked_at=None,
            )
        )
    return ActorContext(
        actor_id=identity_id,
        identity_id=identity_id,
        tenant_id=tenant_id,
        membership_id=membership_id,
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_state=MembershipState.ACTIVE,
        capabilities=capabilities_for(ActorKind.PATRON_ADMIN),
        assigned_case_ids=frozenset(),
        session_id=uuid4(),
        authenticated_at=NOW,
        mfa_verified_at=NOW,
        correlation_id=uuid4(),
    )


def _service(session_factory: sessionmaker[Session]) -> PatronWatchProfileService:
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers=opportunity_watch_profile_handlers(),
    )
    return PatronWatchProfileService(
        session_factory=session_factory,
        dispatcher=dispatcher,
        policy=AuthorizationPolicy(),
    )


def _create_command(profile_id: UUID) -> CreateOpportunityWatchProfileCommand:
    return CreateOpportunityWatchProfileCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        profile_id=profile_id,
        name="Gros œuvre Nord",
        keywords=("réhabilitation",),
        project_types=("REFURBISHMENT",),
        included_departments=("59",),
    )


def test_profile_create_replay_and_version_are_atomic(
    session_factory: sessionmaker[Session],
) -> None:
    actor = _seed_actor(session_factory)
    service = _service(session_factory)
    command = _create_command(uuid4())

    first = service.create(actor=actor, command=command, now=NOW)
    replay = service.create(actor=actor, command=command, now=NOW)
    version_command = AddOpportunityWatchProfileVersionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        profile_id=command.profile_id,
        version_id=uuid4(),
        expected_revision=0,
        name="Gros œuvre Nord — santé",
        keywords=("santé",),
        project_types=("HEALTHCARE",),
    )
    version_result = service.add_version(actor=actor, command=version_command, now=NOW)

    assert first.replayed is False
    assert replay.replayed is True
    assert version_result.replayed is False
    with session_factory() as session:
        profile = session.get(OpportunityWatchProfileRecord, command.profile_id)
        versions = list(
            session.scalars(
                sa.select(OpportunityWatchProfileVersionRecord).where(
                    OpportunityWatchProfileVersionRecord.tenant_id == actor.tenant_id,
                    OpportunityWatchProfileVersionRecord.profile_id == command.profile_id,
                )
            )
        )
        events = list(
            session.scalars(
                sa.select(DomainEventRecord).where(
                    DomainEventRecord.tenant_id == actor.tenant_id,
                    DomainEventRecord.aggregate_id == command.profile_id,
                )
            )
        )
        outbox = list(
            session.scalars(
                sa.select(OutboxMessageRecord).where(
                    OutboxMessageRecord.tenant_id == actor.tenant_id,
                    OutboxMessageRecord.payload_json["profile_id"].astext
                    == str(command.profile_id),
                )
            )
        )
    assert profile is not None
    assert profile.aggregate_revision == 1
    assert profile.current_version == 2
    assert len(versions) == 2
    assert len(events) == 2
    assert len(outbox) == 2


def test_profile_stale_revision_is_rejected(
    session_factory: sessionmaker[Session],
) -> None:
    actor = _seed_actor(session_factory)
    service = _service(session_factory)
    create = _create_command(uuid4())
    service.create(actor=actor, command=create, now=NOW)
    add = AddOpportunityWatchProfileVersionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        profile_id=create.profile_id,
        version_id=uuid4(),
        expected_revision=0,
        keywords=("premier",),
    )
    service.add_version(actor=actor, command=add, now=NOW)

    stale = AddOpportunityWatchProfileVersionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        profile_id=create.profile_id,
        version_id=uuid4(),
        expected_revision=0,
        keywords=("stale",),
    )
    with pytest.raises(CommandExecutionError, match="VERSION_CONFLICT"):
        service.add_version(actor=actor, command=stale, now=NOW)


def test_profile_version_table_is_append_only(
    session_factory: sessionmaker[Session],
) -> None:
    actor = _seed_actor(session_factory)
    service = _service(session_factory)
    command = _create_command(uuid4())
    service.create(actor=actor, command=command, now=NOW)

    with pytest.raises(sa.exc.DBAPIError), session_factory.begin() as session:
        session.execute(
            sa.text(
                "UPDATE opportunity_watch_profile_versions "
                "SET name = 'tampered' WHERE tenant_id = :tenant_id"
            ),
            {"tenant_id": actor.tenant_id},
        )

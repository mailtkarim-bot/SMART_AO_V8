from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.case.application.handlers import CreateCaseHandler
from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.case.infrastructure.repositories import SqlAlchemyCaseRepository
from app.modules.dce.infrastructure.repositories import SqlAlchemyConsultationRepository
from app.modules.opportunity.application.boamp_case_creation import (
    BoampCaseCreationCommand,
    BoampCaseCreationService,
)
from app.modules.opportunity.infrastructure.observation_models import (
    BoampOpportunityObservationRecord,
    BoampOpportunityQualificationRecord,
)
from app.platform.events.dispatcher import CommandContext, CommandDispatcher
from app.platform.persistence.models import (
    CommandReceiptRecord,
    DomainEventRecord,
    OutboxMessageRecord,
    TenantRecord,
)
from app.platform.security.models import IdentityRecord, TenantMembershipRecord
from sqlalchemy.orm import Session, sessionmaker

pytestmark = [pytest.mark.db, pytest.mark.process]
NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


def _dispatcher(session_factory: sessionmaker[Session]) -> CommandDispatcher:
    return CommandDispatcher(
        session_factory=session_factory,
        handlers={
            "CreateCase": CreateCaseHandler(
                repository_factory=SqlAlchemyCaseRepository,
                consultation_reader_factory=SqlAlchemyConsultationRepository,
            )
        },
    )


def _seed_signal(
    engine: sa.Engine,
    *,
    qualified: bool = True,
) -> tuple[UUID, UUID, UUID, UUID]:
    tenant_id = uuid4()
    identity_id = uuid4()
    membership_id = uuid4()
    observation_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            sa.insert(TenantRecord).values(
                id=tenant_id,
                slug=f"boamp-case-{tenant_id.hex[:12]}",
                lifecycle="ACTIVE",
            )
        )
        connection.execute(
            sa.insert(IdentityRecord).values(
                id=identity_id,
                email_normalized=f"patron-{identity_id.hex[:12]}@example.test",
                lifecycle="ACTIVE",
                email_verified_at=NOW,
            )
        )
        connection.execute(
            sa.insert(TenantMembershipRecord).values(
                id=membership_id,
                tenant_id=tenant_id,
                identity_id=identity_id,
                role="PATRON_ADMIN",
                state="ACTIVE",
                activated_at=NOW,
                revoked_at=None,
            )
        )
        connection.execute(
            sa.insert(BoampOpportunityObservationRecord).values(
                id=observation_id,
                tenant_id=tenant_id,
                source="BOAMP",
                source_notice_id=f"A-{observation_id.hex[:12]}",
                fingerprint_sha256="a" * 64,
                title="Réhabilitation école publique",
                publication_date=date(2026, 8, 20),
                response_deadline=NOW + timedelta(days=14),
                department_codes=["59"],
                market_types=["TRAVAUX"],
                source_status="EN_COURS",
                score_version="BOAMP_PUBLIC_V1",
                score=92,
                score_explanation_json={"public_relevance": 92},
                score_explanation_sha256="b" * 64,
                observed_at=NOW,
            )
        )
        if qualified:
            connection.execute(
                sa.insert(BoampOpportunityQualificationRecord).values(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    observation_id=observation_id,
                    actor_id=identity_id,
                    decision="QUALIFIED",
                    reason_code="RELEVANT_PUBLIC_SIGNAL",
                    score_snapshot=92,
                    score_version="BOAMP_PUBLIC_V1",
                    command_id=uuid4(),
                    idempotency_key=uuid4(),
                    correlation_id=None,
                )
            )
    return tenant_id, identity_id, membership_id, observation_id


def _context(*, tenant_id: UUID, identity_id: UUID, membership_id: UUID) -> CommandContext:
    return CommandContext(
        tenant_id=tenant_id,
        actor_id=identity_id,
        actor_kind="PATRON_ADMIN",
        received_at=NOW,
        identity_id=identity_id,
        membership_id=membership_id,
        session_id=uuid4(),
        correlation_id=uuid4(),
    )


def _command(
    *, observation_id: UUID, idempotency_key: UUID | None = None
) -> BoampCaseCreationCommand:
    return BoampCaseCreationCommand(
        observation_id=observation_id,
        command_id=uuid4(),
        idempotency_key=idempotency_key or uuid4(),
        correlation_id=uuid4(),
    )


def test_qualified_signal_creates_one_case_and_replays_durably(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, membership_id, observation_id = _seed_signal(database_engine)
    service = BoampCaseCreationService(
        session_factory=session_factory,
        dispatcher=_dispatcher(session_factory),
    )
    context = _context(
        tenant_id=tenant_id,
        identity_id=identity_id,
        membership_id=membership_id,
    )
    command = _command(observation_id=observation_id)

    first = service.create(context=context, command=command, now=NOW)
    replay = service.create(context=context, command=command, now=NOW)

    assert first.status == "SUCCEEDED"
    assert first.replayed is False
    assert replay.replayed is True
    assert replay.event_ids == first.event_ids
    assert len(first.aggregate_refs) == 1
    case_id = UUID(str(first.aggregate_refs[0]["aggregate_id"]))
    with session_factory() as session:
        case = session.get(CaseRecord, case_id)
        assert case is not None
        assert case.tenant_id == tenant_id
        assert case.business_origin == "OPPORTUNITY"
        assert case.origin_reference_id == observation_id
        assert session.scalar(
            sa.select(sa.func.count(CommandReceiptRecord.id)).where(
                CommandReceiptRecord.tenant_id == tenant_id,
                CommandReceiptRecord.idempotency_key == command.idempotency_key,
            )
        ) == 1
        assert session.scalar(
            sa.select(sa.func.count(DomainEventRecord.id)).where(
                DomainEventRecord.tenant_id == tenant_id,
                DomainEventRecord.event_type == "CASE_CREATED",
            )
        ) == 1
        assert session.scalar(
            sa.select(sa.func.count(OutboxMessageRecord.id)).where(
                OutboxMessageRecord.tenant_id == tenant_id,
                OutboxMessageRecord.event_id == UUID(first.event_ids[0]),
            )
        ) == 1


def test_case_creation_requires_a_qualified_signal(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, membership_id, observation_id = _seed_signal(
        database_engine,
        qualified=False,
    )
    service = BoampCaseCreationService(
        session_factory=session_factory,
        dispatcher=_dispatcher(session_factory),
    )

    with pytest.raises(ValueError, match="BOAMP_QUALIFICATION_REQUIRED"):
        service.create(
            context=_context(
                tenant_id=tenant_id,
                identity_id=identity_id,
                membership_id=membership_id,
            ),
            command=_command(observation_id=observation_id),
            now=NOW,
        )

    with session_factory() as session:
        assert session.scalar(
            sa.select(sa.func.count(CaseRecord.id)).where(CaseRecord.tenant_id == tenant_id)
        ) == 0
        assert session.scalar(
            sa.select(sa.func.count(CommandReceiptRecord.id)).where(
                CommandReceiptRecord.tenant_id == tenant_id
            )
        ) == 0


def test_case_creation_does_not_cross_tenant_boundary(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    source_tenant, _identity_id, _membership_id, observation_id = _seed_signal(database_engine)
    foreign_tenant, foreign_identity, foreign_membership, _ = _seed_signal(database_engine)
    service = BoampCaseCreationService(
        session_factory=session_factory,
        dispatcher=_dispatcher(session_factory),
    )

    with pytest.raises(PermissionError, match="NOT_FOUND_OR_FORBIDDEN"):
        service.create(
            context=_context(
                tenant_id=foreign_tenant,
                identity_id=foreign_identity,
                membership_id=foreign_membership,
            ),
            command=_command(observation_id=observation_id),
            now=NOW,
        )

    with session_factory() as session:
        assert session.scalar(
            sa.select(sa.func.count(CaseRecord.id)).where(
                CaseRecord.tenant_id.in_([source_tenant, foreign_tenant])
            )
        ) == 0

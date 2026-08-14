import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.commands import (
    AmendCaseAssignmentScopeCommand,
    CreateCaseAssignmentCommand,
)
from app.modules.membership.application.patron_assignment import (
    PatronAssignmentManagementService,
    patron_assignment_handlers,
)
from app.platform.events.dispatcher import CommandDispatcher
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord, TenantRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import Capability, capabilities_for
from app.platform.security.context import ActorContext, ActorKind, MembershipState
from app.platform.security.models import (
    CaseAssignmentChangeEventRecord,
    CaseAssignmentRecord,
    IdentityRecord,
    TenantMembershipRecord,
)
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = os.getenv("SMART_AO_TEST_DATABASE_URL") or (
    "postgresql+psycopg://"
    + "smart_ao"
    + ":"
    + "smart_ao"
    + "@127.0.0.1:5432/smart_ao"
)
NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def database_engine() -> sa.Engine:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(config, "head")
    engine = sa.create_engine(DATABASE_URL)
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(config, "base")


@pytest.fixture
def session_factory(database_engine: sa.Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=database_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def isolate_patron_assignment_management(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_case_and_memberships(
    session_factory: sessionmaker[Session],
) -> tuple[ActorContext, UUID, UUID]:
    tenant_id = uuid4()
    patron_identity_id = uuid4()
    patron_membership_id = uuid4()
    collaborator_identity_id = uuid4()
    collaborator_membership_id = uuid4()
    case_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            TenantRecord(
                id=tenant_id,
                slug=f"tenant-{tenant_id.hex[:12]}",
                lifecycle="ACTIVE",
            )
        )
        session.add_all(
            (
                IdentityRecord(
                    id=patron_identity_id,
                    email_normalized=f"patron-{patron_identity_id.hex[:12]}@example.test",
                    lifecycle="ACTIVE",
                    email_verified_at=NOW,
                ),
                IdentityRecord(
                    id=collaborator_identity_id,
                    email_normalized=(
                        f"collaborator-{collaborator_identity_id.hex[:12]}@example.test"
                    ),
                    lifecycle="ACTIVE",
                    email_verified_at=NOW,
                ),
            )
        )
        session.add_all(
            (
                TenantMembershipRecord(
                    id=patron_membership_id,
                    tenant_id=tenant_id,
                    identity_id=patron_identity_id,
                    role="PATRON_ADMIN",
                    state="ACTIVE",
                    activated_at=NOW,
                    revoked_at=None,
                ),
                TenantMembershipRecord(
                    id=collaborator_membership_id,
                    tenant_id=tenant_id,
                    identity_id=collaborator_identity_id,
                    role="COLLABORATEUR",
                    state="ACTIVE",
                    activated_at=NOW,
                    revoked_at=None,
                ),
            )
        )
        session.flush()
        session.add(
            CaseRecord(
                id=case_id,
                tenant_id=tenant_id,
                aggregate_revision=3,
                functional_identity_hash="a" * 64,
                title="Affaire patron",
                object_description=None,
                business_origin="MANUAL",
                origin_reference_id=None,
                origin_rationale="Préparation d’une réponse DCE",
                consultation_id=None,
                scope_kind="CUSTOM",
                scope_json={},
                scope_fingerprint="b" * 64,
                applicable_dce_version_id=None,
                lifecycle="ACTIVE",
                commercial_stage="ANALYSIS",
                decision_readiness="NOT_ASSESSED",
                dce_freshness="NO_DCE",
                responsibility_status="UNASSIGNED",
                stopped_reason=None,
                stopped_at=None,
                archived_reason=None,
                archived_at=None,
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )

    actor = ActorContext(
        actor_id=patron_identity_id,
        identity_id=patron_identity_id,
        tenant_id=tenant_id,
        membership_id=patron_membership_id,
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_state=MembershipState.ACTIVE,
        capabilities=capabilities_for(ActorKind.PATRON_ADMIN),
        assigned_case_ids=frozenset(),
        session_id=uuid4(),
        authenticated_at=NOW,
        mfa_verified_at=NOW,
        correlation_id=uuid4(),
        assignment_scopes=(),
    )
    return actor, case_id, collaborator_membership_id


def _service(session_factory: sessionmaker[Session]) -> PatronAssignmentManagementService:
    return PatronAssignmentManagementService(
        session_factory=session_factory,
        dispatcher=CommandDispatcher(
            session_factory=session_factory,
            handlers=patron_assignment_handlers(),
        ),
        policy=AuthorizationPolicy(),
    )


def _command(case_id: UUID, target_membership_id: UUID) -> CreateCaseAssignmentCommand:
    return CreateCaseAssignmentCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        assignment_id=uuid4(),
        case_id=case_id,
        target_membership_id=target_membership_id,
        expected_case_revision=3,
        scope_actions=[Capability.CASE_DCE_READ.value, Capability.ASSIGNMENT_HISTORY_READ.value],
        scope_classifications=["INTERNAL_OPERATIONAL"],
        starts_at=NOW,
        ends_at=NOW + timedelta(days=7),
    )


def _amend_command(
    assignment_id: UUID,
    *,
    expected_revision: int = 0,
    scope_actions: list[str] | None = None,
) -> AmendCaseAssignmentScopeCommand:
    return AmendCaseAssignmentScopeCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        assignment_id=assignment_id,
        expected_revision=expected_revision,
        scope_actions=scope_actions
        or [Capability.CASE_DCE_READ.value, Capability.PREPARATION_TRANSMIT.value],
        scope_classifications=["INTERNAL_OPERATIONAL"],
    )


@pytest.mark.db
@pytest.mark.security
def test_patron_creation_writes_append_only_change_event_and_outbox(session_factory) -> None:
    actor, case_id, target_membership_id = _seed_case_and_memberships(session_factory)
    command = _command(case_id, target_membership_id)

    result = _service(session_factory).create(actor=actor, command=command, now=NOW)

    assert result.result_code == "CASE_ASSIGNMENT_CREATED"
    with session_factory() as session:
        assignment = session.get(CaseAssignmentRecord, command.assignment_id)
        changes = list(session.scalars(sa.select(CaseAssignmentChangeEventRecord)))
        events = list(session.scalars(sa.select(DomainEventRecord)))
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))
    assert assignment is not None
    assert assignment.state == "ACTIVE"
    assert assignment.aggregate_revision == 0
    assert assignment.membership_id == target_membership_id
    assert assignment.granted_by_membership_id == actor.membership_id
    assert len(changes) == 1
    assert changes[0].event_type == "ASSIGNMENT_CREATED"
    assert changes[0].previous_revision is None
    assert changes[0].resulting_revision == 0
    assert changes[0].resulting_scope_actions_json == [
        Capability.ASSIGNMENT_HISTORY_READ.value,
        Capability.CASE_DCE_READ.value,
    ]
    assert len(events) == 1
    assert events[0].event_type == "CaseAssignmentCreated"
    assert len(outbox) == 1

    with pytest.raises(DBAPIError), session_factory.begin() as session:
        stored = session.get(CaseAssignmentChangeEventRecord, changes[0].id)
        assert stored is not None
        stored.event_type = "ASSIGNMENT_ENDED"


@pytest.mark.db
@pytest.mark.security
def test_patron_creation_replay_has_no_duplicate_change_or_event(session_factory) -> None:
    actor, case_id, target_membership_id = _seed_case_and_memberships(session_factory)
    command = _command(case_id, target_membership_id)
    service = _service(session_factory)

    first = service.create(actor=actor, command=command, now=NOW)
    replay = service.create(actor=actor, command=command, now=NOW)

    assert first.result_code == "CASE_ASSIGNMENT_CREATED"
    assert replay.replayed is True
    with session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(CaseAssignmentRecord)) == 1
        assert session.scalar(
            sa.select(sa.func.count()).select_from(CaseAssignmentChangeEventRecord)
        ) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(DomainEventRecord)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(OutboxMessageRecord)) == 1


@pytest.mark.db
@pytest.mark.security
def test_patron_creation_accepts_a_future_operational_window(session_factory) -> None:
    actor, case_id, target_membership_id = _seed_case_and_memberships(session_factory)
    command = _command(case_id, target_membership_id).model_copy(
        update={
            "starts_at": NOW + timedelta(days=2),
            "ends_at": NOW + timedelta(days=9),
        }
    )

    result = _service(session_factory).create(actor=actor, command=command, now=NOW)

    assert result.result_code == "CASE_ASSIGNMENT_CREATED"
    with session_factory() as session:
        assignment = session.get(CaseAssignmentRecord, command.assignment_id)
    assert assignment is not None
    assert assignment.state == "ACTIVE"
    assert assignment.starts_at == NOW + timedelta(days=2)


@pytest.mark.db
@pytest.mark.security
def test_case_revision_conflict_leaves_no_durable_assignment_side_effect(session_factory) -> None:
    actor, case_id, target_membership_id = _seed_case_and_memberships(session_factory)
    command = _command(case_id, target_membership_id).model_copy(
        update={"expected_case_revision": 2}
    )

    with pytest.raises(Exception, match="CASE_VERSION_CONFLICT"):
        _service(session_factory).create(actor=actor, command=command, now=NOW)

    with session_factory() as session:
        assert session.scalar(sa.select(CaseAssignmentRecord)) is None
        assert session.scalar(sa.select(CaseAssignmentChangeEventRecord)) is None
        assert session.scalar(sa.select(DomainEventRecord)) is None
        assert session.scalar(sa.select(OutboxMessageRecord)) is None


@pytest.mark.db
@pytest.mark.security
def test_open_assignment_is_unique_and_foreign_target_is_neutral(session_factory) -> None:
    actor, case_id, target_membership_id = _seed_case_and_memberships(session_factory)
    service = _service(session_factory)
    service.create(actor=actor, command=_command(case_id, target_membership_id), now=NOW)

    with pytest.raises(Exception, match="ASSIGNMENT_ALREADY_OPEN"):
        service.create(actor=actor, command=_command(case_id, target_membership_id), now=NOW)

    foreign_command = _command(case_id, uuid4())
    with pytest.raises(Exception, match="NOT_FOUND_OR_FORBIDDEN"):
        service.create(actor=actor, command=foreign_command, now=NOW)

    with session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(CaseAssignmentRecord)) == 1
        assert session.scalar(
            sa.select(sa.func.count()).select_from(CaseAssignmentChangeEventRecord)
        ) == 1


@pytest.mark.db
@pytest.mark.security
def test_non_patron_is_denied_before_dispatch_without_assignment_write(session_factory) -> None:
    actor, case_id, target_membership_id = _seed_case_and_memberships(session_factory)
    collaborator_actor = replace(
        actor,
        actor_kind=ActorKind.COLLABORATEUR,
        capabilities=capabilities_for(ActorKind.COLLABORATEUR),
    )

    with pytest.raises(PermissionError, match="ASSIGNMENT_PATRON_REQUIRED"):
        _service(session_factory).create(
            actor=collaborator_actor,
            command=_command(case_id, target_membership_id),
            now=NOW,
        )

    with session_factory() as session:
        assert session.scalar(sa.select(CaseAssignmentRecord)) is None
        assert session.scalar(sa.select(CaseAssignmentChangeEventRecord)) is None


@pytest.mark.db
@pytest.mark.security
def test_patron_amends_scope_with_revisioned_change_event_and_outbox(session_factory) -> None:
    actor, case_id, target_membership_id = _seed_case_and_memberships(session_factory)
    service = _service(session_factory)
    creation = _command(case_id, target_membership_id)
    service.create(actor=actor, command=creation, now=NOW)
    amendment = _amend_command(creation.assignment_id)

    result = service.amend_scope(actor=actor, command=amendment, now=NOW)

    assert result.result_code == "CASE_ASSIGNMENT_SCOPE_AMENDED"
    with session_factory() as session:
        assignment = session.get(CaseAssignmentRecord, creation.assignment_id)
        changes = list(
            session.scalars(
                sa.select(CaseAssignmentChangeEventRecord).where(
                    CaseAssignmentChangeEventRecord.assignment_id == creation.assignment_id,
                    CaseAssignmentChangeEventRecord.event_type == "ASSIGNMENT_SCOPE_AMENDED",
                )
            )
        )
        events = list(session.scalars(sa.select(DomainEventRecord)))
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))
    assert assignment is not None
    assert assignment.aggregate_revision == 1
    assert assignment.scope_actions_json == [
        Capability.CASE_DCE_READ.value,
        Capability.PREPARATION_TRANSMIT.value,
    ]
    assert len(changes) == 1
    assert changes[0].previous_revision == 0
    assert changes[0].resulting_revision == 1
    assert changes[0].previous_scope_actions_json == [
        Capability.ASSIGNMENT_HISTORY_READ.value,
        Capability.CASE_DCE_READ.value,
    ]
    assert len(events) == 2
    assert events[-1].event_type == "CaseAssignmentScopeAmended"
    assert len(outbox) == 2


@pytest.mark.db
@pytest.mark.security
def test_patron_scope_amendment_replays_without_second_durable_change(session_factory) -> None:
    actor, case_id, target_membership_id = _seed_case_and_memberships(session_factory)
    service = _service(session_factory)
    creation = _command(case_id, target_membership_id)
    service.create(actor=actor, command=creation, now=NOW)
    amendment = _amend_command(creation.assignment_id)

    first = service.amend_scope(actor=actor, command=amendment, now=NOW)
    replay = service.amend_scope(actor=actor, command=amendment, now=NOW)

    assert first.result_code == "CASE_ASSIGNMENT_SCOPE_AMENDED"
    assert replay.replayed is True
    with session_factory() as session:
        assignment = session.get(CaseAssignmentRecord, creation.assignment_id)
        changes = list(session.scalars(sa.select(CaseAssignmentChangeEventRecord)))
        events = list(session.scalars(sa.select(DomainEventRecord)))
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))
    assert assignment is not None
    assert assignment.aggregate_revision == 1
    assert len(changes) == 2
    assert len(events) == 2
    assert len(outbox) == 2


@pytest.mark.db
@pytest.mark.security
def test_patron_scope_amendment_rejects_unchanged_or_stale_scope(session_factory) -> None:
    actor, case_id, target_membership_id = _seed_case_and_memberships(session_factory)
    service = _service(session_factory)
    creation = _command(case_id, target_membership_id)
    service.create(actor=actor, command=creation, now=NOW)

    with pytest.raises(Exception, match="ASSIGNMENT_SCOPE_UNCHANGED"):
        service.amend_scope(
            actor=actor,
            command=_amend_command(
                creation.assignment_id,
                scope_actions=[
                    Capability.ASSIGNMENT_HISTORY_READ.value,
                    Capability.CASE_DCE_READ.value,
                ],
            ),
            now=NOW,
        )
    service.amend_scope(actor=actor, command=_amend_command(creation.assignment_id), now=NOW)
    with pytest.raises(Exception, match="VERSION_CONFLICT"):
        service.amend_scope(
            actor=actor,
            command=_amend_command(
                creation.assignment_id,
                expected_revision=0,
                scope_actions=[Capability.CASE_DCE_READ.value],
            ),
            now=NOW,
        )

    with session_factory() as session:
        assignment = session.get(CaseAssignmentRecord, creation.assignment_id)
        assert assignment is not None
        assert assignment.aggregate_revision == 1
        assert session.scalar(
            sa.select(sa.func.count()).select_from(CaseAssignmentChangeEventRecord)
        ) == 2


@pytest.mark.db
@pytest.mark.security
def test_patron_amends_suspended_assignment_without_reactivating_it(session_factory) -> None:
    actor, case_id, target_membership_id = _seed_case_and_memberships(session_factory)
    service = _service(session_factory)
    creation = _command(case_id, target_membership_id)
    service.create(actor=actor, command=creation, now=NOW)
    with session_factory.begin() as session:
        assignment = session.get(CaseAssignmentRecord, creation.assignment_id)
        assert assignment is not None
        assignment.state = "SUSPENDED"

    result = service.amend_scope(
        actor=actor,
        command=_amend_command(creation.assignment_id),
        now=NOW,
    )

    assert result.result_code == "CASE_ASSIGNMENT_SCOPE_AMENDED"
    with session_factory() as session:
        assignment = session.get(CaseAssignmentRecord, creation.assignment_id)
    assert assignment is not None
    assert assignment.state == "SUSPENDED"
    assert assignment.aggregate_revision == 1

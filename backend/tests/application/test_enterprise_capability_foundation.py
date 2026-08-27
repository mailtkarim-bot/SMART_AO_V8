from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.enterprise.application.enterprise_capability import (
    EnterpriseCapabilityService,
    enterprise_capability_handlers,
)
from app.modules.enterprise.application.enterprise_capability_commands import (
    AddEnterpriseCapabilityVersionCommand,
    CreateEnterpriseCapabilityCommand,
)
from app.modules.enterprise.application.enterprise_commands import (
    CreateEnterpriseCompanyCommand,
    RegisterEnterpriseDocumentCommand,
)
from app.modules.enterprise.application.enterprise_library import (
    EnterpriseLibraryService,
    enterprise_library_handlers,
)
from app.modules.enterprise.infrastructure.capability_context_reader import (
    SqlAlchemyEnterpriseCapabilityContextReader,
)
from app.modules.enterprise.infrastructure.models import EnterpriseDocumentUploadRecord
from app.platform.events.dispatcher import (
    CommandDispatcher,
    CommandExecutionError,
)
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord, TenantRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import capabilities_for
from app.platform.security.context import ActorContext, ActorKind, MembershipState
from app.platform.security.models import (
    EnterpriseCapabilityProofLinkRecord,
    EnterpriseCapabilityRecord,
    EnterpriseCapabilityVersionRecord,
    IdentityRecord,
    TenantMembershipRecord,
)
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)






@pytest.fixture(autouse=True)
def isolate_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_actor(
    session_factory: sessionmaker[Session], *, actor_kind: ActorKind = ActorKind.PATRON_ADMIN
) -> ActorContext:
    tenant_id = uuid4()
    identity_id = uuid4()
    membership_id = uuid4()
    role = "PATRON_ADMIN" if actor_kind is ActorKind.PATRON_ADMIN else "COLLABORATEUR"
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
                role=role,
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
        actor_kind=actor_kind,
        membership_state=MembershipState.ACTIVE,
        capabilities=capabilities_for(actor_kind),
        assigned_case_ids=frozenset(),
        session_id=uuid4(),
        authenticated_at=NOW,
        mfa_verified_at=NOW,
        correlation_id=uuid4(),
        assignment_scopes=(),
    )


def _company_command(*, company_id: UUID) -> CreateEnterpriseCompanyCommand:
    return CreateEnterpriseCompanyCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        company_id=company_id,
        legal_name="Bâtiments Karim SAS",
        trade_name="SMART BÂTIMENT",
        siren="123456789",
        siret="12345678900011",
        vat_number="FR12123456789",
        address_line1="12 rue des Métiers",
        postal_code="75001",
        city="Paris",
        country_code="FR",
    )


def _document_command(*, company_id: UUID, document_id: UUID) -> RegisterEnterpriseDocumentCommand:
    return RegisterEnterpriseDocumentCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        company_id=company_id,
        document_id=document_id,
        expected_revision=0,
        document_kind="INSURANCE",
        document_label="Attestation responsabilité civile",
        storage_object_id=uuid4(),
        original_filename="assurance.pdf",
        issued_at=NOW,
        expires_at=NOW + timedelta(days=365),
        sha256="a" * 64,
        verification_status="PENDING",
    )


def _seed_clean_upload(
    session_factory: sessionmaker[Session],
    actor: ActorContext,
    command: RegisterEnterpriseDocumentCommand,
) -> None:
    with session_factory.begin() as session:
        session.add(
            EnterpriseDocumentUploadRecord(
                id=command.storage_object_id,
                tenant_id=actor.tenant_id,
                company_id=command.company_id,
                document_id=command.document_id,
                document_kind=command.document_kind,
                document_label=command.document_label,
                original_filename=command.original_filename,
                storage_key=f"{actor.tenant_id}/{command.document_id}/{command.storage_object_id}.bin",
                expected_byte_size=10,
                actual_byte_size=10,
                sha256=command.sha256,
                media_type="application/pdf",
                state="CLEAN",
                scan_verdict="CLEAN",
                scanner_name="test-scanner",
                scanner_signature_version="test-1",
                scanned_at=NOW,
                expires_at=NOW + timedelta(hours=1),
                created_by_membership_id=actor.membership_id,
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=command.correlation_id,
            )
        )


def _services(
    session_factory: sessionmaker[Session],
) -> tuple[EnterpriseLibraryService, EnterpriseCapabilityService]:
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={**enterprise_library_handlers(), **enterprise_capability_handlers()},
    )
    policy = AuthorizationPolicy()
    return (
        EnterpriseLibraryService(
            session_factory=session_factory, dispatcher=dispatcher, policy=policy
        ),
        EnterpriseCapabilityService(
            session_factory=session_factory,
            capability_context_reader=SqlAlchemyEnterpriseCapabilityContextReader(
                session_factory
            ),
            dispatcher=dispatcher,
            policy=policy,
        ),
    )


def _create_company_and_proof(
    session_factory: sessionmaker[Session], actor: ActorContext
) -> tuple[UUID, UUID]:
    company_id = uuid4()
    library, _ = _services(session_factory)
    library.create_company(actor=actor, command=_company_command(company_id=company_id), now=NOW)
    document_command = _document_command(company_id=company_id, document_id=uuid4())
    _seed_clean_upload(session_factory, actor, document_command)
    library.register_document(actor=actor, command=document_command, now=NOW)
    return company_id, document_command.document_id


def _create_capability_command(
    *, company_id: UUID, capability_id: UUID
) -> CreateEnterpriseCapabilityCommand:
    return CreateEnterpriseCapabilityCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        company_id=company_id,
        capability_id=capability_id,
        capability_kind="QUALIFICATION",
        name="Qualibat 2142",
        summary="Qualification de travaux de rénovation énergétique",
    )


def _version_command(
    *, capability_id: UUID, proof_id: UUID, expected_revision: int = 0
) -> AddEnterpriseCapabilityVersionCommand:
    return AddEnterpriseCapabilityVersionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        capability_id=capability_id,
        version_id=uuid4(),
        expected_revision=expected_revision,
        title="Qualibat 2142 — version 2026",
        description="Qualification vérifiée pour le périmètre travaux déclaré.",
        valid_from=NOW,
        valid_until=NOW + timedelta(days=365),
        usage_scope="Références et réponses techniques BTP attribuées",
        proof_document_ids=(proof_id,),
    )


@pytest.mark.db
@pytest.mark.security
def test_capability_foundation_persists_version_proof_event_and_outbox(
    session_factory: sessionmaker[Session],
) -> None:
    actor = _seed_actor(session_factory)
    company_id, proof_id = _create_company_and_proof(session_factory, actor)
    _, service = _services(session_factory)
    capability_id = uuid4()

    created = service.create_capability(
        actor=actor,
        command=_create_capability_command(company_id=company_id, capability_id=capability_id),
        now=NOW,
    )
    versioned = service.add_version(
        actor=actor,
        command=_version_command(capability_id=capability_id, proof_id=proof_id),
        now=NOW,
    )
    projection = service.read_capabilities(actor=actor, company_id=company_id, now=NOW)

    assert created.result_code == "ENTERPRISE_CAPABILITY_CREATED"
    assert versioned.result_code == "ENTERPRISE_CAPABILITY_VERSION_ADDED"
    assert projection[0].versions[0].proof_document_ids == (proof_id,)
    with session_factory() as session:
        capability = session.get(EnterpriseCapabilityRecord, capability_id)
        assert capability is not None
        assert capability.aggregate_revision == 1
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(EnterpriseCapabilityVersionRecord)
            )
            == 1
        )
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(EnterpriseCapabilityProofLinkRecord)
            )
            == 1
        )
        events = list(session.scalars(sa.select(DomainEventRecord)))
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))
    assert len(events) == 4
    assert len(outbox) == 4
    assert all("description" not in event.payload_json["data"] for event in events)
    assert all("proof_document_ids" not in message.payload_json["data"] for message in outbox)


@pytest.mark.db
@pytest.mark.security
def test_capability_and_version_replays_are_idempotent(
    session_factory: sessionmaker[Session],
) -> None:
    actor = _seed_actor(session_factory)
    company_id, proof_id = _create_company_and_proof(session_factory, actor)
    _, service = _services(session_factory)
    capability_command = _create_capability_command(company_id=company_id, capability_id=uuid4())
    first = service.create_capability(actor=actor, command=capability_command, now=NOW)
    replay = service.create_capability(actor=actor, command=capability_command, now=NOW)
    version_command = _version_command(
        capability_id=capability_command.capability_id, proof_id=proof_id
    )
    version_first = service.add_version(actor=actor, command=version_command, now=NOW)
    version_replay = service.add_version(actor=actor, command=version_command, now=NOW)

    assert first.result_code == "ENTERPRISE_CAPABILITY_CREATED"
    assert replay.replayed is True
    assert version_first.result_code == "ENTERPRISE_CAPABILITY_VERSION_ADDED"
    assert version_replay.replayed is True
    with session_factory() as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(EnterpriseCapabilityRecord)) == 1
        )
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(EnterpriseCapabilityVersionRecord)
            )
            == 1
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(DomainEventRecord)) == 4


@pytest.mark.db
@pytest.mark.security
def test_capability_version_conflict_and_append_only_are_rejected(
    session_factory: sessionmaker[Session],
) -> None:
    actor = _seed_actor(session_factory)
    company_id, proof_id = _create_company_and_proof(session_factory, actor)
    _, service = _services(session_factory)
    capability_id = uuid4()
    service.create_capability(
        actor=actor,
        command=_create_capability_command(company_id=company_id, capability_id=capability_id),
        now=NOW,
    )
    command = _version_command(capability_id=capability_id, proof_id=proof_id, expected_revision=4)
    with pytest.raises(CommandExecutionError, match="VERSION_CONFLICT"):
        service.add_version(actor=actor, command=command, now=NOW)
    service.add_version(
        actor=actor,
        command=_version_command(capability_id=capability_id, proof_id=proof_id),
        now=NOW,
    )

    with session_factory() as session, pytest.raises(sa.exc.ProgrammingError), session.begin():
        session.execute(
            sa.delete(EnterpriseCapabilityVersionRecord).where(
                EnterpriseCapabilityVersionRecord.capability_id == capability_id
            )
        )


@pytest.mark.db
@pytest.mark.security
def test_expired_or_foreign_proof_cannot_be_attached(
    session_factory: sessionmaker[Session],
) -> None:
    actor = _seed_actor(session_factory)
    company_id, _ = _create_company_and_proof(session_factory, actor)
    _, service = _services(session_factory)
    capability_id = uuid4()
    service.create_capability(
        actor=actor,
        command=_create_capability_command(company_id=company_id, capability_id=capability_id),
        now=NOW,
    )
    with pytest.raises(CommandExecutionError, match="PROOF_NOT_FOUND_OR_FORBIDDEN"):
        service.add_version(
            actor=actor,
            command=_version_command(capability_id=capability_id, proof_id=uuid4()),
            now=NOW,
        )


@pytest.mark.db
@pytest.mark.security
def test_non_patron_and_cross_tenant_reads_are_neutral(
    session_factory: sessionmaker[Session],
) -> None:
    patron = _seed_actor(session_factory)
    collaborator = _seed_actor(session_factory, actor_kind=ActorKind.COLLABORATEUR)
    company_id, _ = _create_company_and_proof(session_factory, patron)
    _, service = _services(session_factory)

    with pytest.raises(PermissionError, match="ENTERPRISE_CAPABILITY_PATRON_REQUIRED"):
        service.read_capabilities(actor=collaborator, company_id=company_id, now=NOW)
    with pytest.raises(PermissionError, match="NOT_FOUND_OR_FORBIDDEN"):
        service.read_capabilities(actor=patron, company_id=collaborator.tenant_id, now=NOW)


@pytest.mark.db
@pytest.mark.security
def test_payload_rejects_duplicate_proof_ids() -> None:
    proof_id = uuid4()
    with pytest.raises(ValueError, match="proof_document_ids"):
        AddEnterpriseCapabilityVersionCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            capability_id=uuid4(),
            version_id=uuid4(),
            expected_revision=0,
            title="Qualification",
            description="Description",
            valid_from=NOW,
            usage_scope="Scope",
            proof_document_ids=(proof_id, proof_id),
        )

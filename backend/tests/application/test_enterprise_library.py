import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.modules.membership.application.enterprise_commands import (
    CreateEnterpriseCompanyCommand,
    RegisterEnterpriseDocumentCommand,
)
from app.modules.membership.application.enterprise_library import (
    EnterpriseLibraryService,
    enterprise_library_handlers,
)
from app.platform.events.dispatcher import CommandDispatcher, CommandExecutionError
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord, TenantRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import capabilities_for
from app.platform.security.context import ActorContext, ActorKind, MembershipState
from app.platform.security.models import (
    EnterpriseCompanyRecord,
    EnterpriseDocumentRecord,
    IdentityRecord,
    TenantMembershipRecord,
)
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
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


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
def isolate_enterprise_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_patron(session_factory: sessionmaker[Session]) -> ActorContext:
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
                email_normalized=f"patron-{identity_id.hex[:12]}@example.test",
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
        assignment_scopes=(),
    )


def _service(session_factory: sessionmaker[Session]) -> EnterpriseLibraryService:
    return EnterpriseLibraryService(
        session_factory=session_factory,
        dispatcher=CommandDispatcher(
            session_factory=session_factory,
            handlers=enterprise_library_handlers(),
        ),
        policy=AuthorizationPolicy(),
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


def _document_command(
    *, company_id: UUID, document_id: UUID, kind: str, expected_revision: int = 0
) -> RegisterEnterpriseDocumentCommand:
    return RegisterEnterpriseDocumentCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        company_id=company_id,
        document_id=document_id,
        expected_revision=expected_revision,
        document_kind=kind,
        document_label={
            "INSURANCE": "Attestation responsabilité civile",
            "KBIS": "Extrait Kbis",
            "RIB": "Relevé d’identité bancaire",
        }[kind],
        storage_object_id=uuid4(),
        original_filename=f"{kind.lower()}.pdf",
        issued_at=NOW,
        expires_at=None if kind == "RIB" else NOW + timedelta(days=365),
        sha256="a" * 64,
        verification_status="PENDING",
    )


@pytest.mark.db
@pytest.mark.security
def test_patron_creates_company_and_registers_enterprise_documents(
    session_factory: sessionmaker[Session],
) -> None:
    actor = _seed_patron(session_factory)
    company_id = uuid4()
    service = _service(session_factory)

    created = service.create_company(
        actor=actor,
        command=_company_command(company_id=company_id),
        now=NOW,
    )
    documents = []
    for expected_revision, kind in enumerate(("INSURANCE", "KBIS", "RIB")):
        documents.append(
            service.register_document(
                actor=actor,
                command=_document_command(
                    company_id=company_id,
                    document_id=uuid4(),
                    kind=kind,
                    expected_revision=expected_revision,
                ),
                now=NOW,
            )
        )

    assert created.result_code == "ENTERPRISE_COMPANY_CREATED"
    assert [item.result_code for item in documents] == [
        "ENTERPRISE_DOCUMENT_REGISTERED",
        "ENTERPRISE_DOCUMENT_REGISTERED",
        "ENTERPRISE_DOCUMENT_REGISTERED",
    ]
    with session_factory() as session:
        company = session.get(EnterpriseCompanyRecord, company_id)
        records = list(session.scalars(sa.select(EnterpriseDocumentRecord)))
        events = list(session.scalars(sa.select(DomainEventRecord)))
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))
    assert company is not None
    assert company.aggregate_revision == 3
    assert {record.document_kind for record in records} == {"INSURANCE", "KBIS", "RIB"}
    assert len(events) == 4
    assert len(outbox) == 4
    assert all("sha256" not in event.payload_json["data"] for event in events)
    assert all("storage_object_id" not in message.payload_json["data"] for message in outbox)


@pytest.mark.db
@pytest.mark.security
def test_replaying_company_command_is_idempotent_without_duplicate_company(
    session_factory: sessionmaker[Session],
) -> None:
    actor = _seed_patron(session_factory)
    command = _company_command(company_id=uuid4())
    service = _service(session_factory)

    first = service.create_company(actor=actor, command=command, now=NOW)
    replay = service.create_company(actor=actor, command=command, now=NOW)

    assert first.result_code == "ENTERPRISE_COMPANY_CREATED"
    assert replay.replayed is True
    with session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(EnterpriseCompanyRecord)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(DomainEventRecord)) == 1


@pytest.mark.db
@pytest.mark.security
def test_company_revision_conflict_does_not_register_second_document(
    session_factory: sessionmaker[Session],
) -> None:
    actor = _seed_patron(session_factory)
    company_id = uuid4()
    service = _service(session_factory)
    service.create_company(actor=actor, command=_company_command(company_id=company_id), now=NOW)
    document = _document_command(company_id=company_id, document_id=uuid4(), kind="KBIS")
    stale = document.model_copy(update={"expected_revision": 99})

    with pytest.raises(CommandExecutionError, match="VERSION_CONFLICT"):
        service.register_document(actor=actor, command=stale, now=NOW)

    with session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(EnterpriseDocumentRecord)) == 0

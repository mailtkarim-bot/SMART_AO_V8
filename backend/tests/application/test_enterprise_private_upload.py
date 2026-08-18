import asyncio
from collections.abc import AsyncIterable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.dce.application.upload import MalwareScanResult, QuarantineWriteResult
from app.modules.enterprise.application.enterprise_library import (
    enterprise_library_handlers,
)
from app.modules.enterprise.application.enterprise_upload import (
    EnterprisePrivateUploadService,
    EnterpriseUploadAlreadyClaimedError,
    EnterpriseUploadRejectedError,
    enterprise_upload_handlers,
)
from app.platform.events.dispatcher import CommandDispatcher
from app.platform.persistence.models import TenantRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import capabilities_for
from app.platform.security.context import ActorContext, ActorKind, MembershipState
from app.platform.security.models import (
    EnterpriseCompanyRecord,
    EnterpriseDocumentRecord,
    EnterpriseDocumentUploadRecord,
    IdentityRecord,
    TenantMembershipRecord,
)
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def write(
        self, *, storage_key: str, stream: AsyncIterable[bytes], max_bytes: int
    ) -> QuarantineWriteResult:
        chunks: list[bytes] = []
        async for chunk in stream:
            chunks.append(chunk)
            if sum(map(len, chunks)) > max_bytes:
                raise EnterpriseUploadRejectedError(status_code=413)
        content = b"".join(chunks)
        self.objects[storage_key] = content
        return QuarantineWriteResult(byte_size=len(content), sha256=sha256(content).hexdigest())

    async def delete(self, *, storage_key: str) -> None:
        self.deleted.append(storage_key)
        self.objects.pop(storage_key, None)


class StaticInspector:
    async def detect_media_type(self, *, storage_key: str) -> str:
        return "application/pdf"


class StaticScanner:
    def __init__(self, verdict: str) -> None:
        self.verdict = verdict
        self.calls = 0

    async def scan(self, *, storage_key: str) -> MalwareScanResult:
        self.calls += 1
        return MalwareScanResult(self.verdict, "test-scanner", "test-1", NOW)






@pytest.fixture(autouse=True)
def isolate(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed(
    session_factory: sessionmaker[Session], *, role: str = "PATRON_ADMIN"
) -> tuple[ActorContext, UUID, UUID, UUID, str]:
    tenant_id, identity_id, membership_id = uuid4(), uuid4(), uuid4()
    company_id, upload_id, document_id = uuid4(), uuid4(), uuid4()
    storage_key = f"{tenant_id}/{document_id}/{upload_id}.bin"
    with session_factory.begin() as session:
        session.add(
            TenantRecord(id=tenant_id, slug=f"tenant-{tenant_id.hex[:12]}", lifecycle="ACTIVE")
        )
        session.add(
            IdentityRecord(
                id=identity_id,
                email_normalized=f"u-{identity_id.hex[:12]}@test",
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
            )
        )
        session.add(
            EnterpriseCompanyRecord(
                id=company_id,
                tenant_id=tenant_id,
                aggregate_revision=0,
                legal_name="BTP SAS",
                trade_name=None,
                siren="123456789",
                siret="12345678900011",
                vat_number="FR12123456789",
                address_line1="1 rue A",
                postal_code="75001",
                city="Paris",
                country_code="FR",
            )
        )
        session.add(
            EnterpriseDocumentUploadRecord(
                id=upload_id,
                tenant_id=tenant_id,
                company_id=company_id,
                document_id=document_id,
                document_kind="KBIS",
                document_label="Kbis",
                original_filename="kbis.pdf",
                storage_key=storage_key,
                expected_byte_size=8,
                state="AWAITING_UPLOAD",
                expires_at=NOW + timedelta(hours=1),
                created_by_membership_id=membership_id,
                command_id=uuid4(),
                idempotency_key=uuid4(),
            )
        )
    actor = ActorContext(
        actor_id=identity_id,
        identity_id=identity_id,
        tenant_id=tenant_id,
        membership_id=membership_id,
        actor_kind=ActorKind.PATRON_ADMIN if role == "PATRON_ADMIN" else ActorKind.COLLABORATEUR,
        membership_state=MembershipState.ACTIVE,
        capabilities=capabilities_for(
            ActorKind.PATRON_ADMIN if role == "PATRON_ADMIN" else ActorKind.COLLABORATEUR
        ),
        assigned_case_ids=frozenset(),
        session_id=uuid4(),
        authenticated_at=NOW,
        mfa_verified_at=NOW,
        correlation_id=uuid4(),
        assignment_scopes=(),
    )
    return actor, company_id, upload_id, document_id, storage_key


def _service(
    session_factory: sessionmaker[Session], storage: MemoryStorage, scanner: StaticScanner
) -> EnterprisePrivateUploadService:
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={**enterprise_upload_handlers(), **enterprise_library_handlers()},
    )
    return EnterprisePrivateUploadService(
        session_factory=session_factory,
        dispatcher=dispatcher,
        policy=AuthorizationPolicy(),
        storage=storage,
        inspector=StaticInspector(),
        scanner=scanner,
        allowed_media_types=frozenset({"application/pdf"}),
        max_bytes=1000,
    )


async def _stream(*chunks: bytes) -> AsyncIterable[bytes]:
    for chunk in chunks:
        yield chunk


@pytest.mark.db
@pytest.mark.integration
def test_private_enterprise_upload_hashes_scans_and_marks_clean(
    session_factory: sessionmaker[Session],
) -> None:
    actor, _, upload_id, _, storage_key = _seed(session_factory)
    storage, scanner = MemoryStorage(), StaticScanner("CLEAN")
    result = asyncio.run(
        _service(session_factory, storage, scanner).upload(
            actor=actor, upload_id=upload_id, stream=_stream(b"%PDF-1.7"), content_length=8
        )
    )
    assert result.state == "CLEAN"
    with session_factory() as session:
        row = session.get(EnterpriseDocumentUploadRecord, upload_id)
        document = (
            session.get(EnterpriseDocumentRecord, UUID(str(row.document_id))) if row else None
        )
    assert (
        row is not None and row.state == "CLEAN" and row.sha256 == sha256(b"%PDF-1.7").hexdigest()
    )
    assert document is not None
    assert document.verification_status == "PENDING"
    assert document.storage_object_id == upload_id
    assert scanner.calls == 1 and storage.objects[storage_key] == b"%PDF-1.7"


@pytest.mark.db
@pytest.mark.integration
@pytest.mark.security
def test_private_enterprise_upload_replays_clean_materialization_without_duplicate(
    session_factory: sessionmaker[Session],
) -> None:
    actor, _, upload_id, _, _ = _seed(session_factory)
    storage, scanner = MemoryStorage(), StaticScanner("CLEAN")
    service = _service(session_factory, storage, scanner)
    first = asyncio.run(
        service.upload(
            actor=actor, upload_id=upload_id, stream=_stream(b"%PDF-1.7"), content_length=8
        )
    )
    replay = asyncio.run(
        service.upload(
            actor=actor, upload_id=upload_id, stream=_stream(b"ignored"), content_length=7
        )
    )
    with session_factory() as session:
        document_count = session.scalar(
            sa.select(sa.func.count()).select_from(EnterpriseDocumentRecord)
        )
    assert first.state == "CLEAN" and replay.state == "CLEAN"
    assert scanner.calls == 1 and document_count == 1


@pytest.mark.db
@pytest.mark.integration
def test_private_enterprise_upload_rejects_scan_and_replay(
    session_factory: sessionmaker[Session],
) -> None:
    actor, _, upload_id, _, _ = _seed(session_factory)
    storage, scanner = MemoryStorage(), StaticScanner("ERROR")
    service = _service(session_factory, storage, scanner)
    with pytest.raises(EnterpriseUploadRejectedError):
        asyncio.run(
            service.upload(
                actor=actor, upload_id=upload_id, stream=_stream(b"%PDF-1.7"), content_length=8
            )
        )
    with pytest.raises(EnterpriseUploadAlreadyClaimedError):
        asyncio.run(
            service.upload(
                actor=actor, upload_id=upload_id, stream=_stream(b"%PDF-1.7"), content_length=8
            )
        )
    assert scanner.calls == 1


@pytest.mark.db
@pytest.mark.integration
def test_collaborator_is_refused_before_private_lookup(
    session_factory: sessionmaker[Session],
) -> None:
    actor, _, upload_id, _, _ = _seed(session_factory, role="COLLABORATEUR")
    with pytest.raises(PermissionError, match="ENTERPRISE_LIBRARY_PATRON_REQUIRED"):
        asyncio.run(
            _service(session_factory, MemoryStorage(), StaticScanner("CLEAN")).upload(
                actor=actor, upload_id=upload_id, stream=_stream(b"%PDF-1.7"), content_length=8
            )
        )

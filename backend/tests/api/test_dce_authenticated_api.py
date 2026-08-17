from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.bootstrap.application import AppRuntime, create_app
from app.interfaces.http.routes.authentication import AuthenticationHttpRuntime
from app.modules.dce.application.upload import DceUploadService, MalwareScanResult
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
from app.modules.dce.infrastructure.models.dce_staging import DceStagedObjectRecord
from app.modules.dce.infrastructure.models.dce_version import (
    DceDocumentRecord,
    DceVersionRecord,
)
from app.modules.dce.infrastructure.quarantine import LocalQuarantineStorageAdapter
from app.platform.persistence.models import CommandReceiptRecord
from app.platform.security.authentication import AuthenticationService
from app.platform.security.models import (
    AuthSessionRecord,
    IdentityRecord,
    SecurityAuditEventRecord,
    TenantMembershipRecord,
)
from app.platform.security.tokens import JwtAccessTokenCodec
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class UnusedPasswordVerifier:
    def verify(self, *, password_hash: str, password: str) -> bool:
        return False


class UploadTestInspector:
    async def detect_media_type(self, *, storage_key: str) -> str:
        return "application/pdf"


class UploadTestScanner:
    async def scan(self, *, storage_key: str) -> MalwareScanResult:
        return MalwareScanResult(
            verdict="CLEAN",
            scanner_name="test-clamd",
            scanner_signature_version="test-signatures",
            scanned_at=NOW,
        )


class UnusedTokenGenerator:
    def generate(self) -> str:
        return "unused-refresh-token"






@pytest.fixture(autouse=True)
def isolate_dce_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_principal(
    engine: sa.Engine,
    *,
    role: str = "PATRON_ADMIN",
    tenant_id: UUID | None = None,
) -> tuple[UUID, UUID, UUID]:
    create_tenant = tenant_id is None
    tenant_id = tenant_id or uuid4()
    identity_id, membership_id, session_id = uuid4(), uuid4(), uuid4()
    with engine.begin() as connection:
        if create_tenant:
            connection.execute(
                sa.text("INSERT INTO tenants (id, slug, lifecycle) VALUES (:id, :slug, 'ACTIVE')"),
                {"id": tenant_id, "slug": f"tenant-{tenant_id.hex[:12]}"},
            )
        connection.execute(
            sa.insert(IdentityRecord).values(
                id=identity_id,
                email_normalized=f"user-{identity_id}@example.test",
                lifecycle="ACTIVE",
                email_verified_at=NOW,
            )
        )
        connection.execute(
            sa.insert(TenantMembershipRecord).values(
                id=membership_id,
                tenant_id=tenant_id,
                identity_id=identity_id,
                role=role,
                state="ACTIVE",
                activated_at=NOW,
                revoked_at=None,
            )
        )
        connection.execute(
            sa.insert(AuthSessionRecord).values(
                id=session_id,
                tenant_id=tenant_id,
                membership_id=membership_id,
                identity_id=identity_id,
                state="ACTIVE",
                auth_strength="PASSWORD",
                token_version=1,
                issued_at=NOW,
                last_seen_at=NOW,
                expires_at=NOW + timedelta(hours=8),
                absolute_expires_at=NOW + timedelta(hours=12),
                mfa_verified_at=None,
                revoked_at=None,
                revoke_reason=None,
            )
        )
    return tenant_id, identity_id, session_id


def _seed_dce(engine: sa.Engine, *, tenant_id: UUID) -> UUID:
    consultation_id, dce_version_id = uuid4(), uuid4()
    with Session(engine) as session:
        session.add(
            ConsultationRecord(
                id=consultation_id,
                tenant_id=tenant_id,
                aggregate_revision=1,
                functional_identity_hash="b" * 64,
                buyer_legal_name="Ville de test",
                buyer_normalized_id="VILLE-TEST",
                external_reference="AO-2026-001",
                object_label="Réhabilitation école",
                location_label="Lille",
                source_channel="MANUAL_UPLOAD",
                source_reference="DCE test",
                source_received_at=NOW,
                lifecycle="OPEN",
                freshness="CURRENT",
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        session.flush()
        session.add(
            DceVersionRecord(
                id=dce_version_id,
                tenant_id=tenant_id,
                aggregate_revision=3,
                consultation_id=consultation_id,
                corpus_hash="a" * 64,
                predecessor_dce_version_id=None,
                provenance_channel="MANUAL_UPLOAD",
                provenance_reference="Forbidden reference",
                provenance_url="https://forbidden.example.test",
                source_received_at=NOW,
                lifecycle="ADMITTED",
                integrity="VERIFIED",
                classification_readiness="CLASSIFIED",
                analysis_readiness="READY_FOR_ANALYSIS",
                withdrawal_source=None,
                withdrawal_reason=None,
                superseded_at=None,
                withdrawn_at=None,
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        session.commit()
    return dce_version_id


def _client(
    session_factory: sessionmaker[Session],
    *,
    dce_upload_service_factory=None,
) -> tuple[TestClient, JwtAccessTokenCodec]:
    clock = FixedClock()
    tokens = JwtAccessTokenCodec(
        signing_key="test-only-signing-key-at-least-32-bytes",
        issuer="smart-ao-test",
        audience="smart-ao-web",
        clock=clock,
    )
    auth_runtime = AuthenticationHttpRuntime.create(
        authentication_service=AuthenticationService(
            session_factory=session_factory,
            password_verifier=UnusedPasswordVerifier(),
            token_generator=UnusedTokenGenerator(),
            clock=clock,
        ),
        session_factory=session_factory,
        access_tokens=tokens,
        csrf_token_generator=UnusedTokenGenerator(),
        clock=clock,
    )
    app = create_app(
        runtime=AppRuntime.create(
            session_factory=session_factory,
            dce_upload_service_factory=dce_upload_service_factory,
        ),
        authentication_runtime=auth_runtime,
    )
    return TestClient(app, base_url="https://smart-ao.test"), tokens


def _headers(
    tokens: JwtAccessTokenCodec,
    *,
    identity_id: UUID,
    session_id: UUID,
) -> dict[str, str]:
    token = tokens.issue(
        identity_id=identity_id,
        session_id=session_id,
        token_version=1,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_metadata_requires_bearer_and_exposes_only_authorized_fields(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, session_id = _seed_principal(database_engine)
    dce_id = _seed_dce(database_engine, tenant_id=tenant_id)
    client, tokens = _client(session_factory)
    assert client.get(f"/api/v1/dce-versions/{dce_id}").status_code == 401
    response = client.get(
        f"/api/v1/dce-versions/{dce_id}",
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(dce_id)
    assert response.json()["integrity"] == "VERIFIED"
    forbidden_fields = {
        "corpus_hash",
        "provenance_url",
        "provenance_reference",
        "storage_key",
        "documents",
    }
    for forbidden in forbidden_fields:
        assert forbidden not in response.json()


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_read_refuses_collaborator_without_case_scope_and_audits(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, session_id = _seed_principal(database_engine, role="COLLABORATEUR")
    dce_id = _seed_dce(database_engine, tenant_id=tenant_id)
    client, tokens = _client(session_factory)
    response = client.get(
        f"/api/v1/dce-versions/{dce_id}",
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )
    assert response.status_code == 403
    with Session(database_engine) as session:
        statement = sa.select(SecurityAuditEventRecord).where(
            SecurityAuditEventRecord.event_type == "AUTHZ_DENIED"
        )
        audit = session.scalar(statement)
    assert audit is not None
    assert audit.resource_id == dce_id


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_read_is_neutral_and_audited_for_other_tenant(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    owner_tenant, _, _ = _seed_principal(database_engine)
    dce_id = _seed_dce(database_engine, tenant_id=owner_tenant)
    _, other_identity, other_session = _seed_principal(database_engine)
    client, tokens = _client(session_factory)
    response = client.get(
        f"/api/v1/dce-versions/{dce_id}",
        headers=_headers(
            tokens,
            identity_id=other_identity,
            session_id=other_session,
        ),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "NOT_FOUND_OR_FORBIDDEN"
    with Session(database_engine) as session:
        statement = sa.select(SecurityAuditEventRecord).where(
            SecurityAuditEventRecord.event_type == "AUTHZ_DENIED",
            SecurityAuditEventRecord.actor_id == other_identity,
            SecurityAuditEventRecord.resource_id == dce_id,
        )
        audit = session.scalar(statement)
    assert audit is not None
    assert audit.reason_code == "NOT_FOUND_OR_FORBIDDEN"


def _seed_consultation(engine: sa.Engine, *, tenant_id: UUID, revision: int = 4) -> UUID:
    consultation_id = uuid4()
    with Session(engine) as session:
        session.add(
            ConsultationRecord(
                id=consultation_id,
                tenant_id=tenant_id,
                aggregate_revision=revision,
                functional_identity_hash="d" * 64,
                buyer_legal_name="Ville de test",
                buyer_normalized_id="VILLE-TEST",
                external_reference="AO-2026-ADMISSION",
                object_label="Réhabilitation école",
                location_label="Lille",
                source_channel="MANUAL_UPLOAD",
                source_reference="DCE admission test",
                source_received_at=NOW,
                lifecycle="OPEN",
                freshness="CURRENT",
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        session.commit()
    return consultation_id


def _admission_payload(
    *,
    consultation_id: UUID,
    consultation_revision: int = 4,
) -> dict[str, object]:
    document_hashes = ["b" * 64, "c" * 64]
    canonical_manifest = "\n".join(sorted(document_hashes))
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "dce_version_id": str(uuid4()),
        "consultation_id": str(consultation_id),
        "consultation_revision": consultation_revision,
        "corpus_hash": sha256(canonical_manifest.encode("ascii")).hexdigest(),
        "provenance_channel": "MANUAL_UPLOAD",
        "provenance_reference": "Import pilote",
        "provenance_url": "https://buyer.example.test/dce/2026-01",
        "source_received_at": NOW.isoformat(),
        "documents": [
            {
                "document_id": str(uuid4()),
                "storage_object_id": str(uuid4()),
            },
            {
                "document_id": str(uuid4()),
                "storage_object_id": str(uuid4()),
            },
        ],
    }


def _seed_clean_staged_objects(
    engine: sa.Engine,
    *,
    tenant_id: UUID,
    consultation_id: UUID,
    storage_object_ids: list[UUID],
) -> None:
    document_metadata = (
        ("b" * 64, "Reglement-consultation.pdf", 100),
        ("c" * 64, "CCTP.pdf", 200),
    )
    with Session(engine) as session:
        for storage_object_id, (document_hash, filename, byte_size) in zip(
            storage_object_ids,
            document_metadata,
            strict=True,
        ):
            session.add(
                DceStagedObjectRecord(
                    id=storage_object_id,
                    tenant_id=tenant_id,
                    consultation_id=consultation_id,
                    storage_key=f"dce-staging/{tenant_id}/{storage_object_id}",
                    original_filename=filename,
                    expected_byte_size=byte_size,
                    actual_byte_size=byte_size,
                    sha256=document_hash,
                    media_type="application/pdf",
                    source_channel="MANUAL_UPLOAD",
                    state="CLEAN",
                    scan_verdict="CLEAN",
                    scanner_name="test-scanner",
                    scanner_signature_version="test-signatures",
                    scanned_at=NOW,
                    rejection_code=None,
                    expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
                    consumed_by_dce_version_id=None,
                    consumed_at=None,
                    created_by_actor_id=None,
                    updated_by_actor_id=None,
                )
            )
        session.commit()


def _storage_object_ids(payload: dict[str, object]) -> list[UUID]:
    documents = payload["documents"]
    assert isinstance(documents, list)
    return [UUID(str(document["storage_object_id"])) for document in documents]


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_admission_requires_bearer_and_returns_a_safe_success_receipt(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, session_id = _seed_principal(database_engine)
    consultation_id = _seed_consultation(database_engine, tenant_id=tenant_id)
    payload = _admission_payload(consultation_id=consultation_id)
    _seed_clean_staged_objects(
        database_engine,
        tenant_id=tenant_id,
        consultation_id=consultation_id,
        storage_object_ids=_storage_object_ids(payload),
    )
    client, tokens = _client(session_factory)

    assert client.post("/api/v1/dce-versions", json=payload).status_code == 401

    response = client.post(
        "/api/v1/dce-versions",
        json=payload,
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["result_code"] == "DCE_VERSION_REGISTERED"
    assert body["replayed"] is False
    assert body["aggregate_refs"] == [
        {
            "aggregate_type": "DCE",
            "aggregate_id": payload["dce_version_id"],
            "aggregate_revision": 0,
        }
    ]
    forbidden_fields = {
        "corpus_hash",
        "provenance_url",
        "provenance_reference",
        "storage_object_id",
        "storage_key",
        "documents",
    }
    assert forbidden_fields.isdisjoint(body)
    with Session(database_engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(DceVersionRecord)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(DceDocumentRecord)) == 2
        assert session.scalar(sa.select(sa.func.count()).select_from(CommandReceiptRecord)) == 1


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_admission_replays_the_saved_receipt_without_duplicate_documents(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, session_id = _seed_principal(database_engine)
    consultation_id = _seed_consultation(database_engine, tenant_id=tenant_id)
    payload = _admission_payload(consultation_id=consultation_id)
    _seed_clean_staged_objects(
        database_engine,
        tenant_id=tenant_id,
        consultation_id=consultation_id,
        storage_object_ids=_storage_object_ids(payload),
    )
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)

    first = client.post("/api/v1/dce-versions", json=payload, headers=headers)
    replay = client.post("/api/v1/dce-versions", json=payload, headers=headers)

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["event_ids"] == first.json()["event_ids"]
    with Session(database_engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(DceVersionRecord)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(DceDocumentRecord)) == 2


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_admission_refuses_collaborator_without_case_scope_and_audits(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, _, _ = _seed_principal(database_engine)
    consultation_id = _seed_consultation(database_engine, tenant_id=tenant_id)
    _, collaborator_identity, collaborator_session = _seed_principal(
        database_engine,
        role="COLLABORATEUR",
        tenant_id=tenant_id,
    )
    client, tokens = _client(session_factory)

    response = client.post(
        "/api/v1/dce-versions",
        json=_admission_payload(consultation_id=consultation_id),
        headers=_headers(
            tokens,
            identity_id=collaborator_identity,
            session_id=collaborator_session,
        ),
    )

    assert response.status_code == 403
    with Session(database_engine) as session:
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord).where(
                SecurityAuditEventRecord.event_type == "AUTHZ_DENIED",
                SecurityAuditEventRecord.actor_id == collaborator_identity,
                SecurityAuditEventRecord.resource_id == consultation_id,
            )
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(DceVersionRecord)) == 0
    assert audit is not None


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_admission_is_neutral_and_audited_for_other_tenant(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    owner_tenant, _, _ = _seed_principal(database_engine)
    consultation_id = _seed_consultation(database_engine, tenant_id=owner_tenant)
    _, other_identity, other_session = _seed_principal(database_engine)
    client, tokens = _client(session_factory)

    response = client.post(
        "/api/v1/dce-versions",
        json=_admission_payload(consultation_id=consultation_id),
        headers=_headers(tokens, identity_id=other_identity, session_id=other_session),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "NOT_FOUND_OR_FORBIDDEN"
    with Session(database_engine) as session:
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord).where(
                SecurityAuditEventRecord.event_type == "AUTHZ_DENIED",
                SecurityAuditEventRecord.actor_id == other_identity,
                SecurityAuditEventRecord.resource_id == consultation_id,
            )
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(DceVersionRecord)) == 0
    assert audit is not None
    assert audit.reason_code == "NOT_FOUND_OR_FORBIDDEN"


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_admission_rejected_command_leaves_no_durable_side_effect(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, session_id = _seed_principal(database_engine)
    consultation_id = _seed_consultation(database_engine, tenant_id=tenant_id)
    payload = _admission_payload(consultation_id=consultation_id)
    _seed_clean_staged_objects(
        database_engine,
        tenant_id=tenant_id,
        consultation_id=consultation_id,
        storage_object_ids=_storage_object_ids(payload),
    )
    payload["corpus_hash"] = "a" * 64
    client, tokens = _client(session_factory)

    response = client.post(
        "/api/v1/dce-versions",
        json=payload,
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "COMMAND_REJECTED"
    with Session(database_engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(DceVersionRecord)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(DceDocumentRecord)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(CommandReceiptRecord)) == 0
        assert session.scalar(
            sa.select(sa.func.count()).select_from(DceStagedObjectRecord).where(
                DceStagedObjectRecord.state == "CLEAN"
            )
        ) == 2



def _staging_payload(*, consultation_id: UUID, consultation_revision: int = 4) -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "consultation_id": str(consultation_id),
        "consultation_revision": consultation_revision,
        "original_filename": "Reglement-consultation.pdf",
        "expected_byte_size": 100,
        "source_channel": "MANUAL_UPLOAD",
        "expires_at": (datetime.now(tz=UTC) + timedelta(hours=1)).isoformat(),
    }


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_staging_preparation_requires_bearer_replays_and_never_exposes_storage_key(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, session_id = _seed_principal(database_engine)
    consultation_id = _seed_consultation(database_engine, tenant_id=tenant_id)
    payload = _staging_payload(consultation_id=consultation_id)
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)

    assert client.post("/api/v1/dce-staged-objects", json=payload).status_code == 401

    first = client.post("/api/v1/dce-staged-objects", json=payload, headers=headers)
    replay = client.post("/api/v1/dce-staged-objects", json=payload, headers=headers)

    assert first.status_code == 201
    assert replay.status_code == 200
    body = first.json()
    assert body["result_code"] == "DCE_STAGING_PREPARED"
    assert body["staging"]["state"] == "AWAITING_UPLOAD"
    assert body["staging"]["expires_at"] == str(payload["expires_at"]).replace(
        "+00:00", "Z"
    )
    assert replay.json()["replayed"] is True
    assert replay.json()["event_ids"] == first.json()["event_ids"]
    assert "storage_key" not in body
    with Session(database_engine) as session:
        staged_object = session.get(
            DceStagedObjectRecord,
            UUID(body["staging"]["storage_object_id"]),
        )
    assert staged_object is not None
    assert staged_object.state == "AWAITING_UPLOAD"
    assert staged_object.storage_key == f"dce-staging/{tenant_id}/{staged_object.id}"


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_staging_refuses_collaborator_without_case_scope_and_audits(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, _, _ = _seed_principal(database_engine)
    consultation_id = _seed_consultation(database_engine, tenant_id=tenant_id)
    _, collaborator_identity, collaborator_session = _seed_principal(
        database_engine,
        role="COLLABORATEUR",
        tenant_id=tenant_id,
    )
    client, tokens = _client(session_factory)

    response = client.post(
        "/api/v1/dce-staged-objects",
        json=_staging_payload(consultation_id=consultation_id),
        headers=_headers(
            tokens,
            identity_id=collaborator_identity,
            session_id=collaborator_session,
        ),
    )

    assert response.status_code == 403
    with Session(database_engine) as session:
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord).where(
                SecurityAuditEventRecord.event_type == "AUTHZ_DENIED",
                SecurityAuditEventRecord.actor_id == collaborator_identity,
                SecurityAuditEventRecord.resource_id == consultation_id,
            )
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(DceStagedObjectRecord)) == 0
    assert audit is not None


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_staging_is_neutral_and_audited_for_other_tenant(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    owner_tenant, _, _ = _seed_principal(database_engine)
    consultation_id = _seed_consultation(database_engine, tenant_id=owner_tenant)
    _, other_identity, other_session = _seed_principal(database_engine)
    client, tokens = _client(session_factory)

    response = client.post(
        "/api/v1/dce-staged-objects",
        json=_staging_payload(consultation_id=consultation_id),
        headers=_headers(tokens, identity_id=other_identity, session_id=other_session),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "NOT_FOUND_OR_FORBIDDEN"
    with Session(database_engine) as session:
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord).where(
                SecurityAuditEventRecord.event_type == "AUTHZ_DENIED",
                SecurityAuditEventRecord.actor_id == other_identity,
                SecurityAuditEventRecord.resource_id == consultation_id,
            )
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(DceStagedObjectRecord)) == 0
    assert audit is not None
    assert audit.reason_code == "NOT_FOUND_OR_FORBIDDEN"


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_staging_rejects_client_supplied_storage_object_id(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, session_id = _seed_principal(database_engine)
    consultation_id = _seed_consultation(database_engine, tenant_id=tenant_id)
    payload = _staging_payload(consultation_id=consultation_id)
    payload["storage_object_id"] = str(uuid4())
    client, tokens = _client(session_factory)

    response = client.post(
        "/api/v1/dce-staged-objects",
        json=payload,
        headers=_headers(tokens, identity_id=identity_id, session_id=session_id),
    )

    assert response.status_code == 422
    with Session(database_engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(DceStagedObjectRecord)) == 0



def _upload_service_factory(root: Path):
    def factory(dispatcher):
        storage = LocalQuarantineStorageAdapter(root=root)
        return DceUploadService(
            dispatcher=dispatcher,
            storage=storage,
            inspector=UploadTestInspector(),
            scanner=UploadTestScanner(),
            allowed_media_types=frozenset({"application/pdf"}),
        )

    return factory


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_upload_requires_bearer_streams_to_quarantine_and_returns_no_storage_facts(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    content = b"%PDF-" + (b"A" * 95)
    tenant_id, identity_id, session_id = _seed_principal(database_engine)
    consultation_id = _seed_consultation(database_engine, tenant_id=tenant_id)
    client, tokens = _client(
        session_factory,
        dce_upload_service_factory=_upload_service_factory(tmp_path),
    )
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    staging_payload = _staging_payload(consultation_id=consultation_id)
    staging_payload["expected_byte_size"] = len(content)
    prepared = client.post("/api/v1/dce-staged-objects", json=staging_payload, headers=headers)
    assert prepared.status_code == 201
    storage_object_id = prepared.json()["staging"]["storage_object_id"]

    assert client.put(
        f"/api/v1/dce-staged-objects/{storage_object_id}/content",
        content=content,
        headers={"Idempotency-Key": str(uuid4())},
    ).status_code == 401

    response = client.put(
        f"/api/v1/dce-staged-objects/{storage_object_id}/content",
        content=content,
        headers={
            **headers,
            "Idempotency-Key": str(uuid4()),
            "Content-Type": "application/octet-stream",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"storage_object_id": storage_object_id, "state": "CLEAN"}
    with Session(database_engine) as session:
        staged_object = session.get(DceStagedObjectRecord, UUID(storage_object_id))
    assert staged_object is not None
    assert staged_object.state == "CLEAN"
    assert staged_object.sha256 == sha256(content).hexdigest()
    assert staged_object.media_type == "application/pdf"
    assert (tmp_path / staged_object.storage_key).read_bytes() == content


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_upload_refuses_collaborator_without_case_scope_and_audits(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    tenant_id, patron_identity, patron_session = _seed_principal(database_engine)
    consultation_id = _seed_consultation(database_engine, tenant_id=tenant_id)
    _, collaborator_identity, collaborator_session = _seed_principal(
        database_engine,
        role="COLLABORATEUR",
        tenant_id=tenant_id,
    )
    client, tokens = _client(
        session_factory,
        dce_upload_service_factory=_upload_service_factory(tmp_path),
    )
    prepared = client.post(
        "/api/v1/dce-staged-objects",
        json=_staging_payload(consultation_id=consultation_id),
        headers=_headers(tokens, identity_id=patron_identity, session_id=patron_session),
    )
    assert prepared.status_code == 201
    storage_object_id = prepared.json()["staging"]["storage_object_id"]

    response = client.put(
        f"/api/v1/dce-staged-objects/{storage_object_id}/content",
        content=b"%PDF-" + (b"A" * 95),
        headers={
            **_headers(
                tokens,
                identity_id=collaborator_identity,
                session_id=collaborator_session,
            ),
            "Idempotency-Key": str(uuid4()),
        },
    )

    assert response.status_code == 403
    with Session(database_engine) as session:
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord).where(
                SecurityAuditEventRecord.event_type == "AUTHZ_DENIED",
                SecurityAuditEventRecord.actor_id == collaborator_identity,
                SecurityAuditEventRecord.resource_id == consultation_id,
            )
        )
        staged_object = session.get(DceStagedObjectRecord, UUID(storage_object_id))
    assert audit is not None
    assert staged_object is not None
    assert staged_object.state == "AWAITING_UPLOAD"


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_dce_upload_is_neutral_for_other_tenant_and_rejects_json_body(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    owner_tenant, owner_identity, owner_session = _seed_principal(database_engine)
    consultation_id = _seed_consultation(database_engine, tenant_id=owner_tenant)
    _, other_identity, other_session = _seed_principal(database_engine)
    client, tokens = _client(
        session_factory,
        dce_upload_service_factory=_upload_service_factory(tmp_path),
    )
    prepared = client.post(
        "/api/v1/dce-staged-objects",
        json=_staging_payload(consultation_id=consultation_id),
        headers=_headers(tokens, identity_id=owner_identity, session_id=owner_session),
    )
    assert prepared.status_code == 201
    storage_object_id = prepared.json()["staging"]["storage_object_id"]

    other_tenant = client.put(
        f"/api/v1/dce-staged-objects/{storage_object_id}/content",
        content=b"%PDF-" + (b"A" * 95),
        headers={
            **_headers(tokens, identity_id=other_identity, session_id=other_session),
            "Idempotency-Key": str(uuid4()),
        },
    )
    assert other_tenant.status_code == 404
    assert other_tenant.json()["detail"] == "NOT_FOUND_OR_FORBIDDEN"

    json_body = client.put(
        f"/api/v1/dce-staged-objects/{storage_object_id}/content",
        json={"not": "binary"},
        headers={
            **_headers(tokens, identity_id=owner_identity, session_id=owner_session),
            "Idempotency-Key": str(uuid4()),
        },
    )
    assert json_body.status_code == 415
    with Session(database_engine) as session:
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord).where(
                SecurityAuditEventRecord.event_type == "AUTHZ_DENIED",
                SecurityAuditEventRecord.actor_id == other_identity,
                SecurityAuditEventRecord.resource_id == consultation_id,
            )
        )
        staged_object = session.get(DceStagedObjectRecord, UUID(storage_object_id))
    assert audit is not None
    assert staged_object is not None
    assert staged_object.state == "AWAITING_UPLOAD"

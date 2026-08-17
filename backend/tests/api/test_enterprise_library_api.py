from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.bootstrap.application import AppRuntime, create_app
from app.interfaces.http.routes.authentication import AuthenticationHttpRuntime
from app.platform.security.authentication import AuthenticationService
from app.platform.security.models import (
    AuthSessionRecord,
    EnterpriseDocumentUploadRecord,
    IdentityRecord,
    TenantMembershipRecord,
)
from app.platform.security.tokens import JwtAccessTokenCodec
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = os.getenv("SMART_AO_TEST_DATABASE_URL") or (
    "postgresql+psycopg://" + "smart_ao" + ":" + "smart_ao" + "@127.0.0.1:5432/smart_ao"
)
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class UnusedPasswordVerifier:
    def verify(self, *, password_hash: str, password: str) -> bool:
        return False


class UnusedTokenGenerator:
    def generate(self) -> str:
        return "unused-refresh-token"


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
def isolate_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_principal(
    engine: sa.Engine,
    *,
    role: str,
    tenant_id: UUID | None = None,
) -> tuple[UUID, UUID, UUID]:
    tenant_id = tenant_id or uuid4()
    identity_id, membership_id, session_id = uuid4(), uuid4(), uuid4()
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO tenants (id, slug, lifecycle) VALUES (:id, :slug, 'ACTIVE') "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tenant_id, "slug": f"tenant-{tenant_id.hex[:12]}"},
        )
        connection.execute(
            sa.insert(IdentityRecord).values(
                id=identity_id,
                email_normalized=f"user-{identity_id.hex[:12]}@example.test",
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


def _client(session_factory: sessionmaker[Session]) -> tuple[TestClient, JwtAccessTokenCodec]:
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
    return (
        TestClient(
            create_app(
                runtime=AppRuntime.create(session_factory=session_factory),
                authentication_runtime=auth_runtime,
            ),
            base_url="https://smart-ao.test",
        ),
        tokens,
    )


def _headers(tokens: JwtAccessTokenCodec, *, identity_id: UUID, session_id: UUID) -> dict[str, str]:
    return {
        "Authorization": (
            "Bearer "
            f"{tokens.issue(identity_id=identity_id, session_id=session_id, token_version=1)}"
        )
    }


def _company_payload() -> dict[str, str]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "legal_name": "Bâtiments Karim SAS",
        "trade_name": "SMART BÂTIMENT",
        "siren": "123456789",
        "siret": "12345678900011",
        "vat_number": "FR12123456789",
        "address_line1": "12 rue des Métiers",
        "postal_code": "75001",
        "city": "Paris",
        "country_code": "FR",
    }


def _document_payload(*, kind: str, expected_revision: int) -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": expected_revision,
        "document_kind": kind,
        "document_label": f"Document {kind}",
        "storage_object_id": str(uuid4()),
        "original_filename": f"{kind.lower()}.pdf",
        "issued_at": NOW.isoformat(),
        "expires_at": None if kind == "RIB" else (NOW + timedelta(days=365)).isoformat(),
        "verification_status": "PENDING",
    }


def _seed_clean_upload(
    session_factory: sessionmaker[Session],
    tenant_id: UUID,
    identity_id: UUID,
    company_id: UUID,
    payload: dict[str, object],
) -> None:
    document_id = uuid5(NAMESPACE_URL, f"enterprise-document:{payload['command_id']}")
    with session_factory.begin() as session:
        membership_id = session.scalar(
            sa.select(TenantMembershipRecord.id).where(
                TenantMembershipRecord.tenant_id == tenant_id,
                TenantMembershipRecord.identity_id == identity_id,
            )
        )
        session.add(
            EnterpriseDocumentUploadRecord(
                id=UUID(str(payload["storage_object_id"])),
                tenant_id=tenant_id,
                company_id=company_id,
                document_id=document_id,
                document_kind=str(payload["document_kind"]),
                document_label=str(payload["document_label"]),
                original_filename=str(payload["original_filename"]),
                storage_key=f"{tenant_id}/{document_id}/{payload['storage_object_id']}.bin",
                expected_byte_size=10,
                actual_byte_size=10,
                sha256="a" * 64,
                media_type="application/pdf",
                state="CLEAN",
                scan_verdict="CLEAN",
                scanner_name="test-scanner",
                scanner_signature_version="test-1",
                scanned_at=NOW,
                expires_at=NOW + timedelta(hours=1),
                created_by_membership_id=membership_id,
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=UUID(str(payload["correlation_id"])),
            )
        )


@pytest.mark.api
@pytest.mark.db
def test_patron_creates_reads_and_registers_enterprise_documents_without_sensitive_leaks(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, session_id = _seed_principal(database_engine, role="PATRON_ADMIN")
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)

    created = client.post(
        "/api/v1/patron/enterprise/company",
        json=_company_payload(),
        headers=headers,
    )
    assert created.status_code == 201
    company_id = created.json()["aggregate_refs"][0]["aggregate_id"]

    for revision, kind in enumerate(("INSURANCE", "KBIS", "RIB")):
        payload = _document_payload(kind=kind, expected_revision=revision)
        _seed_clean_upload(session_factory, tenant_id, identity_id, UUID(company_id), payload)
        response = client.post(
            f"/api/v1/patron/enterprise/companies/{company_id}/documents",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 201
        assert response.json()["result_code"] == "ENTERPRISE_DOCUMENT_REGISTERED"

    read = client.get("/api/v1/patron/enterprise/company", headers=headers)

    assert read.status_code == 200
    body = read.json()
    assert body["company_id"] == company_id
    assert body["aggregate_revision"] == 3
    assert {document["document_kind"] for document in body["documents"]} == {
        "INSURANCE",
        "KBIS",
        "RIB",
    }
    assert "storage_object_id" not in body["documents"][0]
    assert "original_filename" not in body["documents"][0]
    assert "sha256" not in body["documents"][0]
    assert "command_id" not in body["documents"][0]
    assert "idempotency_key" not in body["documents"][0]
    assert tenant_id


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_enterprise_company_create_replays_and_rejects_closed_payload_fields(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    _, identity_id, session_id = _seed_principal(database_engine, role="PATRON_ADMIN")
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    payload = _company_payload()

    first = client.post("/api/v1/patron/enterprise/company", json=payload, headers=headers)
    replay = client.post("/api/v1/patron/enterprise/company", json=payload, headers=headers)
    forbidden_field = client.post(
        "/api/v1/patron/enterprise/company",
        json={**_company_payload(), "tenant_id": str(uuid4())},
        headers=headers,
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert forbidden_field.status_code == 422


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_enterprise_document_route_returns_neutral_conflict_and_collaborator_refusal(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, patron_identity_id, patron_session_id = _seed_principal(
        database_engine, role="PATRON_ADMIN"
    )
    _, collaborator_identity_id, collaborator_session_id = _seed_principal(
        database_engine, role="COLLABORATEUR", tenant_id=tenant_id
    )
    client, tokens = _client(session_factory)
    patron_headers = _headers(tokens, identity_id=patron_identity_id, session_id=patron_session_id)
    collaborator_headers = _headers(
        tokens,
        identity_id=collaborator_identity_id,
        session_id=collaborator_session_id,
    )

    created = client.post(
        "/api/v1/patron/enterprise/company",
        json=_company_payload(),
        headers=patron_headers,
    )
    company_id = created.json()["aggregate_refs"][0]["aggregate_id"]
    stale_payload = _document_payload(kind="KBIS", expected_revision=9)
    _seed_clean_upload(
        session_factory, tenant_id, patron_identity_id, UUID(company_id), stale_payload
    )
    stale = client.post(
        f"/api/v1/patron/enterprise/companies/{company_id}/documents",
        json=stale_payload,
        headers=patron_headers,
    )
    forbidden_read = client.get(
        "/api/v1/patron/enterprise/company",
        headers=collaborator_headers,
    )

    assert stale.status_code == 409
    assert stale.json()["detail"] == "VERSION_CONFLICT"
    assert forbidden_read.status_code == 403
    assert forbidden_read.json()["detail"] == "FORBIDDEN"

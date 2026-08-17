from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.bootstrap.application import AppRuntime, create_app
from app.interfaces.http.routes.authentication import AuthenticationHttpRuntime
from app.platform.security.authentication import AuthenticationService
from app.platform.security.models import AuthSessionRecord, IdentityRecord, TenantMembershipRecord
from app.platform.security.tokens import JwtAccessTokenCodec
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

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


def _capability_payload() -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "capability_kind": "QUALIFICATION",
        "name": "Qualibat 2142",
        "summary": "Qualification de rénovation énergétique",
        "state": "ACTIVE",
    }


def _version_payload(*, expected_revision: int) -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": expected_revision,
        "title": "Qualibat 2142 — version 2026",
        "description": "Qualification vérifiée pour le périmètre déclaré.",
        "valid_from": NOW.isoformat(),
        "valid_until": (NOW + timedelta(days=365)).isoformat(),
        "usage_scope": "Références et réponses techniques BTP attribuées",
        "proof_document_ids": [],
    }


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_creates_versions_reads_capabilities_and_replays(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    _, identity_id, session_id = _seed_principal(database_engine, role="PATRON_ADMIN")
    client, tokens = _client(session_factory)
    headers = _headers(tokens, identity_id=identity_id, session_id=session_id)
    company = client.post(
        "/api/v1/patron/enterprise/company", json=_company_payload(), headers=headers
    )
    company_id = company.json()["aggregate_refs"][0]["aggregate_id"]
    payload = _capability_payload()

    created = client.post(
        f"/api/v1/patron/enterprise/companies/{company_id}/capabilities",
        json=payload,
        headers=headers,
    )
    replay = client.post(
        f"/api/v1/patron/enterprise/companies/{company_id}/capabilities",
        json=payload,
        headers=headers,
    )
    capability_id = created.json()["aggregate_refs"][0]["aggregate_id"]
    version = client.post(
        f"/api/v1/patron/enterprise/capabilities/{capability_id}/versions",
        json=_version_payload(expected_revision=0),
        headers=headers,
    )
    read = client.get(
        f"/api/v1/patron/enterprise/companies/{company_id}/capabilities",
        headers=headers,
    )

    assert company.status_code == 201
    assert created.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert version.status_code == 201
    assert read.status_code == 200
    body = read.json()
    assert body["capabilities"][0]["capability_id"] == capability_id
    assert body["capabilities"][0]["versions"][0]["version_number"] == 1
    assert "command_id" not in body["capabilities"][0]
    assert "tenant_id" not in body["capabilities"][0]
    assert "sha256" not in body["capabilities"][0]


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_capability_routes_reject_closed_payloads_and_collaborator(
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
    company = client.post(
        "/api/v1/patron/enterprise/company", json=_company_payload(), headers=patron_headers
    )
    company_id = company.json()["aggregate_refs"][0]["aggregate_id"]
    closed = client.post(
        f"/api/v1/patron/enterprise/companies/{company_id}/capabilities",
        json={**_capability_payload(), "tenant_id": str(uuid4())},
        headers=patron_headers,
    )
    forbidden = client.get(
        f"/api/v1/patron/enterprise/companies/{company_id}/capabilities",
        headers=collaborator_headers,
    )

    assert closed.status_code == 422
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "FORBIDDEN"

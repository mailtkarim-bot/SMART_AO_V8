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

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


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
def isolate_consultation_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_patron(engine: sa.Engine) -> tuple[UUID, UUID]:
    tenant_id = uuid4()
    identity_id = uuid4()
    membership_id = uuid4()
    auth_session_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            sa.text("INSERT INTO tenants (id, slug, lifecycle) VALUES (:id, :slug, 'ACTIVE')"),
            {"id": tenant_id, "slug": f"tenant-{tenant_id.hex[:12]}"},
        )
        connection.execute(
            sa.insert(IdentityRecord).values(
                id=identity_id,
                email_normalized=f"patron-{identity_id}@example.test",
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
            sa.insert(AuthSessionRecord).values(
                id=auth_session_id,
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
    return identity_id, auth_session_id


def _client(session_factory: sessionmaker[Session]) -> tuple[TestClient, JwtAccessTokenCodec]:
    clock = FixedClock()
    access_tokens = JwtAccessTokenCodec(
        signing_key="test-only-signing-key-at-least-32-bytes",
        issuer="smart-ao-test",
        audience="smart-ao-web",
        clock=clock,
    )
    authentication_runtime = AuthenticationHttpRuntime.create(
        authentication_service=AuthenticationService(
            session_factory=session_factory,
            password_verifier=UnusedPasswordVerifier(),
            token_generator=UnusedTokenGenerator(),
            clock=clock,
        ),
        session_factory=session_factory,
        access_tokens=access_tokens,
        csrf_token_generator=UnusedTokenGenerator(),
        clock=clock,
    )
    app = create_app(
        runtime=AppRuntime.create(session_factory=session_factory),
        authentication_runtime=authentication_runtime,
    )
    return TestClient(app, base_url="https://smart-ao.test"), access_tokens


def _headers(
    access_tokens: JwtAccessTokenCodec,
    *,
    identity_id: UUID,
    session_id: UUID,
) -> dict[str, str]:
    token = access_tokens.issue(identity_id=identity_id, session_id=session_id, token_version=1)
    return {"Authorization": f"Bearer {token}"}


def _payload() -> dict[str, str]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "consultation_id": str(uuid4()),
        "buyer_legal_name": "Ville de test",
        "buyer_normalized_id": "VILLE-TEST",
        "external_reference": "AO-2026-001",
        "object_label": "Réhabilitation école",
        "location_label": "Lille",
        "source_channel": "MANUAL_UPLOAD",
        "source_reference": "Import pilote",
        "source_received_at": "2026-08-13T10:00:00Z",
    }


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_create_consultation_replay_returns_saved_success_with_authenticated_patron(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    identity_id, auth_session_id = _seed_patron(database_engine)
    client, access_tokens = _client(session_factory)
    payload = _payload()
    headers = _headers(
        access_tokens,
        identity_id=identity_id,
        session_id=auth_session_id,
    )

    first = client.post("/api/v1/consultations", json=payload, headers=headers)
    replay = client.post("/api/v1/consultations", json=payload, headers=headers)

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["event_ids"] == first.json()["event_ids"]

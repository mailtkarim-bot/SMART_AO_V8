from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.bootstrap.application import AppRuntime, create_app
from app.interfaces.http.routes.authentication import AuthenticationHttpRuntime
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

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = "postgresql+psycopg://smart_ao:smart_ao@127.0.0.1:5432/smart_ao"
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
def isolate_consultation_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_principal(
    engine: sa.Engine,
    *,
    role: str = "PATRON_ADMIN",
) -> tuple[UUID, UUID, UUID, UUID]:
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
    return tenant_id, identity_id, membership_id, auth_session_id


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
    return (
        TestClient(
            create_app(
                runtime=AppRuntime.create(session_factory=session_factory),
                authentication_runtime=authentication_runtime,
            ),
            base_url="https://smart-ao.test",
        ),
        access_tokens,
    )


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
def test_consultation_routes_require_server_resolved_bearer_context(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    _seed_principal(database_engine)
    client, _ = _client(session_factory)

    response = client.post("/api/v1/consultations", json=_payload())

    assert response.status_code == 401
    assert response.json()["detail"] == "UNAUTHENTICATED"


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_patron_can_create_and_read_consultation_with_authenticated_context(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    _, identity_id, _, auth_session_id = _seed_principal(database_engine)
    client, access_tokens = _client(session_factory)
    payload = _payload()
    headers = _headers(access_tokens, identity_id=identity_id, session_id=auth_session_id)

    created = client.post("/api/v1/consultations", json=payload, headers=headers)
    read = client.get(f"/api/v1/consultations/{payload['consultation_id']}", headers=headers)

    assert created.status_code == 201
    assert read.status_code == 200
    assert read.json()["id"] == payload["consultation_id"]


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_cross_tenant_consultation_read_is_neutral_and_audited(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    _, owner_identity_id, _, owner_session_id = _seed_principal(database_engine)
    _, other_identity_id, _, other_session_id = _seed_principal(database_engine)
    client, access_tokens = _client(session_factory)
    payload = _payload()
    owner_headers = _headers(
        access_tokens,
        identity_id=owner_identity_id,
        session_id=owner_session_id,
    )
    other_headers = _headers(
        access_tokens,
        identity_id=other_identity_id,
        session_id=other_session_id,
    )

    created = client.post(
        "/api/v1/consultations",
        json=payload,
        headers=owner_headers,
    )
    assert created.status_code == 201
    response = client.get(
        f"/api/v1/consultations/{payload['consultation_id']}",
        headers=other_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "NOT_FOUND_OR_FORBIDDEN"
    with Session(database_engine) as session:
        audit_event = session.scalar(
            sa.select(SecurityAuditEventRecord)
            .where(SecurityAuditEventRecord.event_type == "AUTHZ_DENIED")
            .order_by(SecurityAuditEventRecord.occurred_at.desc())
        )
    assert audit_event is not None
    assert audit_event.actor_id == other_identity_id
    assert audit_event.resource_id == UUID(payload["consultation_id"])
    assert audit_event.reason_code == "NOT_FOUND_OR_FORBIDDEN"

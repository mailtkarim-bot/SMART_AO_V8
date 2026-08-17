import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.bootstrap.application import AppRuntime, create_app
from app.interfaces.http.routes.authentication import AuthenticationHttpRuntime
from app.platform.security.authentication import AuthenticationService
from app.platform.security.models import AuthSessionRecord
from app.platform.security.tokens import JwtAccessTokenCodec
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application"))
from test_collab_work_task import _seed  # noqa: E402

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
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))
    return sessionmaker(bind=database_engine, expire_on_commit=False)


def _client(session_factory):
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
    return TestClient(
        create_app(
            runtime=AppRuntime.create(session_factory=session_factory),
            authentication_runtime=auth_runtime,
        ),
        base_url="https://smart-ao.test",
    ), tokens


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_collaborator_task_create_replay_and_read_model(session_factory) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    with session_factory.begin() as session:
        session.add(
            AuthSessionRecord(
                id=actor.session_id,
                tenant_id=actor.tenant_id,
                membership_id=actor.membership_id,
                identity_id=actor.identity_id,
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
    client, tokens = _client(session_factory)
    token = tokens.issue(
        identity_id=actor.identity_id,
        session_id=actor.session_id,
        token_version=1,
    )
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "requirement_id": str(requirement_id),
        "task_kind": "REQUIREMENT_CHECK",
        "title": "Vérifier la pièce de candidature",
        "objective": "Confirmer la source et signaler tout manque.",
    }
    first = client.post(
        f"/api/v1/collaborator/cases/{case_id}/assignments/{assignment_id}/tasks",
        json=payload,
        headers=headers,
    )
    replay = client.post(
        f"/api/v1/collaborator/cases/{case_id}/assignments/{assignment_id}/tasks",
        json=payload,
        headers=headers,
    )
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert "price" not in str(first.json()).lower()
    task_id = first.json()["aggregate_refs"][0]["aggregate_id"]

    listing = client.get(f"/api/v1/collaborator/cases/{case_id}/tasks", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["tasks"][0]["task_id"] == task_id
    assert "financial" not in str(listing.json()).lower()

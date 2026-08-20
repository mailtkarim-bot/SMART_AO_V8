from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.bootstrap.application import create_app
from app.interfaces.http.routes.authentication import AuthenticationHttpRuntime
from app.platform.security.authentication import AuthenticationService
from app.platform.security.models import (
    AuthSessionRecord,
    IdentityRecord,
    PasswordCredentialRecord,
    RefreshTokenRecord,
    TenantMembershipRecord,
)
from app.platform.security.tokens import JwtAccessTokenCodec
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

FIXED_NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return FIXED_NOW


class StubPasswordVerifier:
    def verify(self, *, password_hash: str, password: str) -> bool:
        return password_hash == "$argon2id$fixture" and password == "Correct#Pass123"


class SequenceTokenGenerator:
    def __init__(self, *tokens: str) -> None:
        self._tokens = deque(tokens)

    def generate(self) -> str:
        return self._tokens.popleft()






@pytest.fixture(autouse=True)
def isolate_authentication_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants CASCADE"))


def _insert_tenant(engine: sa.Engine) -> UUID:
    tenant_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            sa.text("INSERT INTO tenants (id, slug, lifecycle) VALUES (:id, :slug, 'ACTIVE')"),
            {"id": tenant_id, "slug": f"tenant-{tenant_id}"},
        )
    return tenant_id


def _active_identity_with_membership(
    engine: sa.Engine,
    *,
    tenant_id: UUID,
) -> tuple[UUID, UUID, str]:
    identity_id = uuid4()
    membership_id = uuid4()
    email = f"patron-{identity_id}@example.test"
    with engine.begin() as connection:
        connection.execute(
            sa.insert(IdentityRecord).values(
                id=identity_id,
                email_normalized=email,
                lifecycle="ACTIVE",
                email_verified_at=FIXED_NOW,
            )
        )
        connection.execute(
            sa.insert(PasswordCredentialRecord).values(
                id=uuid4(),
                identity_id=identity_id,
                password_hash="$argon2id$fixture",
                algorithm="ARGON2ID",
                parameters_version=1,
                changed_at=FIXED_NOW,
                must_change=False,
            )
        )
        connection.execute(
            sa.insert(TenantMembershipRecord).values(
                id=membership_id,
                tenant_id=tenant_id,
                identity_id=identity_id,
                role="PATRON_ADMIN",
                state="ACTIVE",
                activated_at=FIXED_NOW,
                revoked_at=None,
            )
        )
    return identity_id, membership_id, email


def _client(session_factory: sessionmaker[Session]) -> tuple[TestClient, JwtAccessTokenCodec]:
    authentication_service = AuthenticationService(
        session_factory=session_factory,
        password_verifier=StubPasswordVerifier(),
        token_generator=SequenceTokenGenerator("refresh-1", "refresh-2", "refresh-3"),
        clock=FixedClock(),
    )
    access_tokens = JwtAccessTokenCodec(
        signing_key="test-only-signing-key-at-least-32-bytes",
        issuer="smart-ao-test",
        audience="smart-ao-web",
        clock=FixedClock(),
    )
    runtime = AuthenticationHttpRuntime.create(
        authentication_service=authentication_service,
        session_factory=session_factory,
        access_tokens=access_tokens,
        csrf_token_generator=SequenceTokenGenerator("csrf-1", "csrf-2", "csrf-3"),
        clock=FixedClock(),
    )
    app = create_app(authentication_runtime=runtime)
    return TestClient(app, base_url="https://smart-ao.test"), access_tokens


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_login_sets_secure_refresh_and_csrf_cookies_and_returns_short_lived_access_token(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    identity_id, membership_id, email = _active_identity_with_membership(
        database_engine,
        tenant_id=tenant_id,
    )
    client, access_tokens = _client(session_factory)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email.upper(),
            "password": "Correct#Pass123",
            "tenant_id": str(tenant_id),
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "Bearer"
    assert response.json()["expires_in"] == 900
    claims = access_tokens.decode(response.json()["access_token"])
    assert claims.subject == identity_id
    assert claims.session_id is not None
    assert claims.token_version == 1
    assert "role" not in response.json()["access_token"]
    cookies = response.headers.get_list("set-cookie")
    refresh_cookie = next(cookie for cookie in cookies if cookie.startswith("smart_ao_refresh="))
    csrf_cookie = next(cookie for cookie in cookies if cookie.startswith("smart_ao_csrf="))
    assert "HttpOnly" in refresh_cookie
    assert "Secure" in refresh_cookie
    assert "SameSite=lax" in refresh_cookie
    assert "Path=/api/v1/auth" in refresh_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "Secure" in csrf_cookie
    assert "SameSite=strict" in csrf_cookie
    assert "Path=/" in csrf_cookie
    assert "Path=/api/v1/auth" not in csrf_cookie
    assert client.cookies.get("smart_ao_refresh") == "refresh-1"
    assert client.cookies.get("smart_ao_csrf") == "csrf-1"
    with Session(database_engine) as session:
        auth_session = session.get(AuthSessionRecord, claims.session_id)
        assert auth_session is not None
        assert auth_session.membership_id == membership_id


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_login_failure_is_neutral_and_never_sets_authentication_cookies(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    client, _ = _client(session_factory)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "unknown@example.test",
            "password": "Wrong#Pass123",
            "tenant_id": str(tenant_id),
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "INVALID_CREDENTIALS"}
    assert not response.headers.get_list("set-cookie")
    assert client.cookies.get("smart_ao_refresh") is None


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_login_is_rate_limited_after_repeated_failures(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    client, _ = _client(session_factory)
    payload = {
        "email": "unknown@example.test",
        "password": "Wrong#Pass123",
        "tenant_id": str(tenant_id),
    }

    responses = [client.post("/api/v1/auth/login", json=payload) for _ in range(6)]

    assert [response.status_code for response in responses[:5]] == [401] * 5
    assert responses[5].status_code == 429
    assert responses[5].json() == {"detail": "RATE_LIMITED"}
    assert int(responses[5].headers["Retry-After"]) >= 1


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_refresh_requires_matching_csrf_then_rotates_cookies_and_access_token(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    _, _, email = _active_identity_with_membership(database_engine, tenant_id=tenant_id)
    client, access_tokens = _client(session_factory)
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "Correct#Pass123",
            "tenant_id": str(tenant_id),
        },
    )

    rejected = client.post("/api/v1/auth/refresh")
    refreshed = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": client.cookies.get("smart_ao_csrf")},
    )

    assert rejected.status_code == 403
    assert rejected.json() == {"detail": "CSRF_REJECTED"}
    assert refreshed.status_code == 200
    assert client.cookies.get("smart_ao_refresh") == "refresh-2"
    assert client.cookies.get("smart_ao_csrf") == "csrf-2"
    refreshed_session_id = access_tokens.decode(refreshed.json()["access_token"]).session_id
    login_session_id = access_tokens.decode(login.json()["access_token"]).session_id
    assert refreshed_session_id == login_session_id
    with Session(database_engine) as session:
        active_refresh_count = session.scalar(
            sa.select(sa.func.count())
            .select_from(RefreshTokenRecord)
            .where(RefreshTokenRecord.state == "ACTIVE")
        )
        assert active_refresh_count == 1


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_logout_requires_authenticated_context_and_csrf_then_clears_cookies(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    _, _, email = _active_identity_with_membership(database_engine, tenant_id=tenant_id)
    client, _ = _client(session_factory)
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "Correct#Pass123",
            "tenant_id": str(tenant_id),
        },
    )

    missing_csrf = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    logout = client.post(
        "/api/v1/auth/logout",
        headers={
            "Authorization": f"Bearer {login.json()['access_token']}",
            "X-CSRF-Token": client.cookies.get("smart_ao_csrf"),
        },
    )

    assert missing_csrf.status_code == 403
    assert missing_csrf.json() == {"detail": "CSRF_REJECTED"}
    assert logout.status_code == 204
    deleted_cookies = logout.headers.get_list("set-cookie")
    assert any(
        "smart_ao_refresh=" in cookie and "Max-Age=0" in cookie
        for cookie in deleted_cookies
    )
    assert any(
        "smart_ao_csrf=" in cookie and "Max-Age=0" in cookie and "Path=/" in cookie
        for cookie in deleted_cookies
    )


@pytest.mark.api
@pytest.mark.db
@pytest.mark.security
def test_logout_refuses_invalid_access_token_neutrally_without_mutation(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    client, _ = _client(session_factory)

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": "Bearer malformed", "X-CSRF-Token": "anything"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}
    with Session(database_engine) as session:
        assert session.scalar(
            sa.select(sa.func.count())
            .select_from(AuthSessionRecord)
            .where(AuthSessionRecord.tenant_id == tenant_id)
        ) == 0

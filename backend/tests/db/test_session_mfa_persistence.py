from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = os.getenv(
    "SMART_AO_TEST_DATABASE_URL",
    "postgresql+psycopg://smart_ao:smart_ao@127.0.0.1:5432/smart_ao",
)


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
def connection(database_engine: sa.Engine):
    with database_engine.begin() as transaction:
        yield transaction


def _insert_tenant(connection: sa.Connection) -> str:
    tenant_id = str(uuid4())
    connection.execute(
        sa.text("INSERT INTO tenants (id, slug, lifecycle) VALUES (:id, :slug, 'ACTIVE')"),
        {"id": tenant_id, "slug": f"tenant-{tenant_id}"},
    )
    return tenant_id


def _insert_identity(connection: sa.Connection) -> str:
    identity_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO identities (id, email_normalized, lifecycle, email_verified_at)
            VALUES (:id, :email, 'ACTIVE', NOW())
            """
        ),
        {"id": identity_id, "email": f"identity-{identity_id}@example.test"},
    )
    return identity_id


def _insert_membership(
    connection: sa.Connection,
    *,
    tenant_id: str,
    identity_id: str,
) -> str:
    membership_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO tenant_memberships (
                id, tenant_id, identity_id, role, state, activated_at, revoked_at
            ) VALUES (
                :id, :tenant_id, :identity_id, 'PATRON_ADMIN', 'ACTIVE', NOW(), NULL
            )
            """
        ),
        {"id": membership_id, "tenant_id": tenant_id, "identity_id": identity_id},
    )
    return membership_id


def _insert_session(
    connection: sa.Connection,
    *,
    tenant_id: str,
    membership_id: str,
    identity_id: str,
    state: str = "ACTIVE",
    revoked_at: datetime | None = None,
) -> str:
    session_id = str(uuid4())
    issued_at = datetime.now(tz=UTC)
    expires_at = issued_at + timedelta(hours=8)
    absolute_expires_at = issued_at + timedelta(hours=24)
    connection.execute(
        sa.text(
            """
            INSERT INTO auth_sessions (
                id, tenant_id, membership_id, identity_id, state, auth_strength,
                token_version, issued_at, last_seen_at, expires_at, absolute_expires_at,
                mfa_verified_at, revoked_at, revoke_reason
            ) VALUES (
                :id, :tenant_id, :membership_id, :identity_id, :state, 'PASSWORD',
                1, :issued_at, :issued_at, :expires_at, :absolute_expires_at, NULL,
                :revoked_at, :revoke_reason
            )
            """
        ),
        {
            "id": session_id,
            "tenant_id": tenant_id,
            "membership_id": membership_id,
            "identity_id": identity_id,
            "state": state,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "absolute_expires_at": absolute_expires_at,
            "revoked_at": revoked_at,
            "revoke_reason": "LOGOUT" if revoked_at is not None else None,
        },
    )
    return session_id


def _insert_refresh_family(
    connection: sa.Connection,
    *,
    tenant_id: str,
    session_id: str,
) -> str:
    family_id = str(uuid4())
    issued_at = datetime.now(tz=UTC)
    connection.execute(
        sa.text(
            """
            INSERT INTO refresh_token_families (
                id, tenant_id, session_id, state, issued_at, expires_at, revoked_at, revoke_reason
            ) VALUES (
                :id, :tenant_id, :session_id, 'ACTIVE', :issued_at,
                :expires_at, NULL, NULL
            )
            """
        ),
        {
            "id": family_id,
            "tenant_id": tenant_id,
            "session_id": session_id,
            "issued_at": issued_at,
            "expires_at": issued_at + timedelta(days=14),
        },
    )
    return family_id


def _insert_refresh_token(
    connection: sa.Connection,
    *,
    tenant_id: str,
    family_id: str,
    token_hash: str,
    parent_token_id: str | None = None,
) -> str:
    token_id = str(uuid4())
    issued_at = datetime.now(tz=UTC)
    connection.execute(
        sa.text(
            """
            INSERT INTO refresh_tokens (
                id, tenant_id, family_id, parent_token_id, token_hash, state,
                issued_at, expires_at, consumed_at, revoked_at
            ) VALUES (
                :id, :tenant_id, :family_id, :parent_token_id, :token_hash, 'ACTIVE',
                :issued_at, :expires_at, NULL, NULL
            )
            """
        ),
        {
            "id": token_id,
            "tenant_id": tenant_id,
            "family_id": family_id,
            "parent_token_id": parent_token_id,
            "token_hash": token_hash,
            "issued_at": issued_at,
            "expires_at": issued_at + timedelta(days=14),
        },
    )
    return token_id


@pytest.mark.db
def test_migration_creates_session_refresh_and_mfa_tables(database_engine: sa.Engine) -> None:
    inspector = sa.inspect(database_engine)

    assert {
        "auth_sessions",
        "refresh_token_families",
        "refresh_tokens",
        "mfa_factors",
        "mfa_recovery_codes",
    }.issubset(set(inspector.get_table_names()))


@pytest.mark.db
def test_session_membership_reference_is_tenant_scoped(connection: sa.Connection) -> None:
    identity_id = _insert_identity(connection)
    tenant_a = _insert_tenant(connection)
    tenant_b = _insert_tenant(connection)
    membership_a = _insert_membership(
        connection,
        tenant_id=tenant_a,
        identity_id=identity_id,
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_session(
            connection,
            tenant_id=tenant_b,
            membership_id=membership_a,
            identity_id=identity_id,
        )


@pytest.mark.db
def test_session_state_requires_revocation_timestamp_when_revoked(
    connection: sa.Connection,
) -> None:
    identity_id = _insert_identity(connection)
    tenant_id = _insert_tenant(connection)
    membership_id = _insert_membership(
        connection,
        tenant_id=tenant_id,
        identity_id=identity_id,
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_session(
            connection,
            tenant_id=tenant_id,
            membership_id=membership_id,
            identity_id=identity_id,
            state="REVOKED",
        )

    _insert_session(
        connection,
        tenant_id=tenant_id,
        membership_id=membership_id,
        identity_id=identity_id,
        state="REVOKED",
        revoked_at=datetime.now(tz=UTC),
    )


@pytest.mark.db
def test_refresh_family_is_tenant_scoped_to_session(connection: sa.Connection) -> None:
    identity_id = _insert_identity(connection)
    tenant_a = _insert_tenant(connection)
    tenant_b = _insert_tenant(connection)
    membership_a = _insert_membership(
        connection,
        tenant_id=tenant_a,
        identity_id=identity_id,
    )
    session_a = _insert_session(
        connection,
        tenant_id=tenant_a,
        membership_id=membership_a,
        identity_id=identity_id,
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_refresh_family(connection, tenant_id=tenant_b, session_id=session_a)


@pytest.mark.db
def test_refresh_token_hash_is_hash_only_unique_and_one_active_token_per_family(
    connection: sa.Connection,
) -> None:
    identity_id = _insert_identity(connection)
    tenant_id = _insert_tenant(connection)
    membership_id = _insert_membership(
        connection,
        tenant_id=tenant_id,
        identity_id=identity_id,
    )
    session_id = _insert_session(
        connection,
        tenant_id=tenant_id,
        membership_id=membership_id,
        identity_id=identity_id,
    )
    family_id = _insert_refresh_family(connection, tenant_id=tenant_id, session_id=session_id)
    first_token_id = _insert_refresh_token(
        connection,
        tenant_id=tenant_id,
        family_id=family_id,
        token_hash="a" * 64,
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_refresh_token(
            connection,
            tenant_id=tenant_id,
            family_id=family_id,
            token_hash="b" * 64,
        )

    connection.execute(
        sa.text(
            """
            UPDATE refresh_tokens
            SET state = 'ROTATED', consumed_at = NOW()
            WHERE id = :id AND state = 'ACTIVE'
            """
        ),
        {"id": first_token_id},
    )
    second_token_id = _insert_refresh_token(
        connection,
        tenant_id=tenant_id,
        family_id=family_id,
        token_hash="b" * 64,
        parent_token_id=first_token_id,
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_refresh_token(
            connection,
            tenant_id=tenant_id,
            family_id=family_id,
            token_hash="b" * 64,
            parent_token_id=second_token_id,
        )


@pytest.mark.db
def test_refresh_token_can_be_consumed_once_and_replay_revokes_family(
    connection: sa.Connection,
) -> None:
    identity_id = _insert_identity(connection)
    tenant_id = _insert_tenant(connection)
    membership_id = _insert_membership(
        connection,
        tenant_id=tenant_id,
        identity_id=identity_id,
    )
    session_id = _insert_session(
        connection,
        tenant_id=tenant_id,
        membership_id=membership_id,
        identity_id=identity_id,
    )
    family_id = _insert_refresh_family(connection, tenant_id=tenant_id, session_id=session_id)
    token_id = _insert_refresh_token(
        connection,
        tenant_id=tenant_id,
        family_id=family_id,
        token_hash="c" * 64,
    )

    first_use = connection.execute(
        sa.text(
            """
            UPDATE refresh_tokens
            SET state = 'ROTATED', consumed_at = NOW()
            WHERE id = :id AND state = 'ACTIVE' AND consumed_at IS NULL
            """
        ),
        {"id": token_id},
    )
    replay = connection.execute(
        sa.text(
            """
            UPDATE refresh_tokens
            SET state = 'ROTATED', consumed_at = NOW()
            WHERE id = :id AND state = 'ACTIVE' AND consumed_at IS NULL
            """
        ),
        {"id": token_id},
    )
    connection.execute(
        sa.text(
            """
            UPDATE refresh_token_families
            SET state = 'COMPROMISED', revoked_at = NOW(), revoke_reason = 'REFRESH_REPLAY'
            WHERE id = :id AND state = 'ACTIVE'
            """
        ),
        {"id": family_id},
    )

    assert first_use.rowcount == 1
    assert replay.rowcount == 0
    assert connection.scalar(
        sa.text("SELECT state FROM refresh_token_families WHERE id = :id"),
        {"id": family_id},
    ) == "COMPROMISED"


@pytest.mark.db
def test_session_and_refresh_tables_have_no_raw_tokens(database_engine: sa.Engine) -> None:
    inspector = sa.inspect(database_engine)
    session_columns = {column["name"] for column in inspector.get_columns("auth_sessions")}
    refresh_columns = {column["name"] for column in inspector.get_columns("refresh_tokens")}

    assert not {"access_token", "refresh_token", "token_plaintext"} & session_columns
    assert "token_hash" in refresh_columns
    assert not {"refresh_token", "token_plaintext", "token_value"} & refresh_columns


@pytest.mark.db
def test_mfa_factor_requires_verified_timestamp_when_active(connection: sa.Connection) -> None:
    identity_id = _insert_identity(connection)

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                INSERT INTO mfa_factors (
                    id, identity_id, factor_type, state, secret_ciphertext,
                    encryption_key_version, verified_at, disabled_at
                ) VALUES (
                    :id, :identity_id, 'TOTP', 'ACTIVE', :secret, 1, NULL, NULL
                )
                """
            ),
            {"id": str(uuid4()), "identity_id": identity_id, "secret": "ciphertext"},
        )

    connection.execute(
        sa.text(
            """
            INSERT INTO mfa_factors (
                id, identity_id, factor_type, state, secret_ciphertext,
                encryption_key_version, verified_at, disabled_at
            ) VALUES (
                :id, :identity_id, 'TOTP', 'ACTIVE', :secret, 1, NOW(), NULL
            )
            """
        ),
        {"id": str(uuid4()), "identity_id": identity_id, "secret": "ciphertext"},
    )


@pytest.mark.db
def test_only_one_active_totp_factor_is_allowed_per_identity(connection: sa.Connection) -> None:
    identity_id = _insert_identity(connection)
    values = {"identity_id": identity_id, "secret": "ciphertext"}
    connection.execute(
        sa.text(
            """
            INSERT INTO mfa_factors (
                id, identity_id, factor_type, state, secret_ciphertext,
                encryption_key_version, verified_at, disabled_at
            ) VALUES (
                :id, :identity_id, 'TOTP', 'ACTIVE', :secret, 1, NOW(), NULL
            )
            """
        ),
        {"id": str(uuid4()), **values},
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                INSERT INTO mfa_factors (
                    id, identity_id, factor_type, state, secret_ciphertext,
                    encryption_key_version, verified_at, disabled_at
                ) VALUES (
                    :id, :identity_id, 'TOTP', 'ACTIVE', :secret, 1, NOW(), NULL
                )
                """
            ),
            {"id": str(uuid4()), **values},
        )


@pytest.mark.db
def test_recovery_code_is_hash_only_unique_and_consumed_once(connection: sa.Connection) -> None:
    identity_id = _insert_identity(connection)
    factor_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO mfa_factors (
                id, identity_id, factor_type, state, secret_ciphertext,
                encryption_key_version, verified_at, disabled_at
            ) VALUES (
                :id, :identity_id, 'RECOVERY_CODES', 'ACTIVE', NULL, NULL, NOW(), NULL
            )
            """
        ),
        {"id": factor_id, "identity_id": identity_id},
    )
    code_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO mfa_recovery_codes (
                id, identity_id, factor_id, factor_type, code_hash, issued_at, consumed_at
            ) VALUES (
                :id, :identity_id, :factor_id, 'RECOVERY_CODES', :code_hash, NOW(), NULL
            )
            """
        ),
        {
            "id": code_id,
            "identity_id": identity_id,
            "factor_id": factor_id,
            "code_hash": "d" * 64,
        },
    )

    first_use = connection.execute(
        sa.text(
            """
            UPDATE mfa_recovery_codes
            SET consumed_at = NOW()
            WHERE id = :id AND consumed_at IS NULL
            """
        ),
        {"id": code_id},
    )
    replay = connection.execute(
        sa.text(
            """
            UPDATE mfa_recovery_codes
            SET consumed_at = NOW()
            WHERE id = :id AND consumed_at IS NULL
            """
        ),
        {"id": code_id},
    )

    assert first_use.rowcount == 1
    assert replay.rowcount == 0


@pytest.mark.db
def test_mfa_tables_have_no_plaintext_secret_or_recovery_code_column(
    database_engine: sa.Engine,
) -> None:
    inspector = sa.inspect(database_engine)
    factor_columns = {column["name"] for column in inspector.get_columns("mfa_factors")}
    recovery_columns = {
        column["name"] for column in inspector.get_columns("mfa_recovery_codes")
    }

    assert "secret_ciphertext" in factor_columns
    assert not {"totp_secret", "secret_plaintext"} & factor_columns
    assert "code_hash" in recovery_columns
    assert not {"recovery_code", "code_plaintext"} & recovery_columns

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


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


def _insert_identity(
    connection: sa.Connection,
    *,
    email: str | None = None,
    lifecycle: str = "ACTIVE",
) -> str:
    identity_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO identities (id, email_normalized, lifecycle, email_verified_at)
            VALUES (:id, :email, :lifecycle, NOW())
            """
        ),
        {
            "id": identity_id,
            "email": email or f"identity-{identity_id}@example.test",
            "lifecycle": lifecycle,
        },
    )
    return identity_id


def _insert_membership(
    connection: sa.Connection,
    *,
    tenant_id: str,
    identity_id: str,
    role: str = "COLLABORATEUR",
    state: str = "ACTIVE",
) -> str:
    membership_id = str(uuid4())
    activated_at = "NOW()" if state == "ACTIVE" else "NULL"
    revoked_at = "NOW()" if state == "REVOKED" else "NULL"
    connection.execute(
        sa.text(
            f"""
            INSERT INTO tenant_memberships (
                id, tenant_id, identity_id, role, state, activated_at, revoked_at
            ) VALUES (
                :id, :tenant_id, :identity_id, :role, :state, {activated_at}, {revoked_at}
            )
            """
        ),
        {
            "id": membership_id,
            "tenant_id": tenant_id,
            "identity_id": identity_id,
            "role": role,
            "state": state,
        },
    )
    return membership_id


@pytest.mark.db
def test_migration_creates_identity_membership_and_bootstrap_tables(
    database_engine: sa.Engine,
) -> None:
    inspector = sa.inspect(database_engine)

    assert {
        "identities",
        "password_credentials",
        "tenant_memberships",
        "tenant_bootstrap_tokens",
    }.issubset(set(inspector.get_table_names()))


@pytest.mark.db
def test_identity_email_is_normalized_and_unique(connection: sa.Connection) -> None:
    _insert_identity(connection, email="patron@example.test")

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_identity(connection, email="patron@example.test")

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_identity(connection, email="PATRON@example.test")


@pytest.mark.db
def test_identity_lifecycle_is_constrained(connection: sa.Connection) -> None:
    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_identity(connection, lifecycle="UNKNOWN")


@pytest.mark.db
def test_password_credential_is_one_to_one_and_argon2id_only(connection: sa.Connection) -> None:
    identity_id = _insert_identity(connection)
    credential_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO password_credentials (
                id, identity_id, password_hash, algorithm,
                parameters_version, changed_at, must_change
            ) VALUES (
                :id, :identity_id, :password_hash, 'ARGON2ID', 1, NOW(), false
            )
            """
        ),
        {
            "id": credential_id,
            "identity_id": identity_id,
            "password_hash": "$argon2id$v=19$m=65536,t=3,p=1$test$safehash",
        },
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                INSERT INTO password_credentials (
                    id, identity_id, password_hash, algorithm,
                    parameters_version, changed_at, must_change
                ) VALUES (
                    :id, :identity_id, :password_hash, 'ARGON2ID', 1, NOW(), false
                )
                """
            ),
            {
                "id": str(uuid4()),
                "identity_id": identity_id,
                "password_hash": "$argon2id$v=19$m=65536,t=3,p=1$other$hash",
            },
        )

    other_identity_id = _insert_identity(connection)
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                INSERT INTO password_credentials (
                    id, identity_id, password_hash, algorithm,
                    parameters_version, changed_at, must_change
                ) VALUES (
                    :id, :identity_id, :password_hash, 'SHA256', 1, NOW(), false
                )
                """
            ),
            {
                "id": str(uuid4()),
                "identity_id": other_identity_id,
                "password_hash": "not-an-argon2-hash",
            },
        )


@pytest.mark.db
def test_password_credential_table_has_no_plaintext_password_column(
    database_engine: sa.Engine,
) -> None:
    columns = {
        column["name"] for column in sa.inspect(database_engine).get_columns("password_credentials")
    }

    assert "password_hash" in columns
    assert not {"password", "plaintext_password", "password_secret"} & columns


@pytest.mark.db
def test_membership_is_unique_per_identity_and_tenant(connection: sa.Connection) -> None:
    tenant_id = _insert_tenant(connection)
    identity_id = _insert_identity(connection)
    _insert_membership(connection, tenant_id=tenant_id, identity_id=identity_id)

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_membership(connection, tenant_id=tenant_id, identity_id=identity_id)

    other_tenant_id = _insert_tenant(connection)
    _insert_membership(connection, tenant_id=other_tenant_id, identity_id=identity_id)


@pytest.mark.db
def test_membership_state_and_timestamps_are_constrained(connection: sa.Connection) -> None:
    tenant_id = _insert_tenant(connection)
    identity_id = _insert_identity(connection)

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                INSERT INTO tenant_memberships (id, tenant_id, identity_id, role, state)
                VALUES (:id, :tenant_id, :identity_id, 'COLLABORATEUR', 'ACTIVE')
                """
            ),
            {"id": str(uuid4()), "tenant_id": tenant_id, "identity_id": identity_id},
        )

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                INSERT INTO tenant_memberships (
                    id, tenant_id, identity_id, role, state, activated_at, revoked_at
                ) VALUES (
                    :id, :tenant_id, :identity_id, 'COLLABORATEUR', 'REVOKED', NOW(), NULL
                )
                """
            ),
            {"id": str(uuid4()), "tenant_id": tenant_id, "identity_id": identity_id},
        )


@pytest.mark.db
def test_only_one_active_patron_admin_is_allowed_per_tenant(connection: sa.Connection) -> None:
    tenant_id = _insert_tenant(connection)
    _insert_membership(
        connection,
        tenant_id=tenant_id,
        identity_id=_insert_identity(connection),
        role="PATRON_ADMIN",
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_membership(
            connection,
            tenant_id=tenant_id,
            identity_id=_insert_identity(connection),
            role="PATRON_ADMIN",
        )

    _insert_membership(
        connection,
        tenant_id=tenant_id,
        identity_id=_insert_identity(connection),
        role="PATRON_DELEGATE",
    )


@pytest.mark.db
def test_bootstrap_token_is_hash_only_expiring_and_consumed_once(connection: sa.Connection) -> None:
    tenant_id = _insert_tenant(connection)
    token_id = str(uuid4())
    issued_at = datetime.now(tz=UTC)
    expires_at = issued_at + timedelta(hours=1)
    connection.execute(
        sa.text(
            """
            INSERT INTO tenant_bootstrap_tokens (
                id, tenant_id, token_hash, issued_at, expires_at, consumed_at
            ) VALUES (
                :id, :tenant_id, :token_hash, :issued_at, :expires_at, NULL
            )
            """
        ),
        {
            "id": token_id,
            "tenant_id": tenant_id,
            "token_hash": "a" * 64,
            "issued_at": issued_at,
            "expires_at": expires_at,
        },
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                INSERT INTO tenant_bootstrap_tokens (
                    id, tenant_id, token_hash, issued_at, expires_at, consumed_at
                ) VALUES (
                    :id, :tenant_id, :token_hash, :issued_at, :expires_at, NULL
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": tenant_id,
                "token_hash": "b" * 64,
                "issued_at": issued_at,
                "expires_at": expires_at,
            },
        )

    first_consumption = connection.execute(
        sa.text(
            """
            UPDATE tenant_bootstrap_tokens
            SET consumed_at = NOW()
            WHERE id = :id AND consumed_at IS NULL
            """
        ),
        {"id": token_id},
    )
    repeated_consumption = connection.execute(
        sa.text(
            """
            UPDATE tenant_bootstrap_tokens
            SET consumed_at = NOW()
            WHERE id = :id AND consumed_at IS NULL
            """
        ),
        {"id": token_id},
    )

    assert first_consumption.rowcount == 1
    assert repeated_consumption.rowcount == 0


@pytest.mark.db
def test_bootstrap_token_requires_future_expiry(connection: sa.Connection) -> None:
    tenant_id = _insert_tenant(connection)
    issued_at = datetime.now(tz=UTC)

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                INSERT INTO tenant_bootstrap_tokens (
                    id, tenant_id, token_hash, issued_at, expires_at, consumed_at
                ) VALUES (
                    :id, :tenant_id, :token_hash, :issued_at, :expires_at, NULL
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": tenant_id,
                "token_hash": "c" * 64,
                "issued_at": issued_at,
                "expires_at": issued_at,
            },
        )

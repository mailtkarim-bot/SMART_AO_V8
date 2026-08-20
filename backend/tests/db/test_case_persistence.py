from __future__ import annotations

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
        sa.text(
            """
            INSERT INTO tenants (id, slug, lifecycle)
            VALUES (:id, :slug, 'ACTIVE')
            """
        ),
        {"id": tenant_id, "slug": f"tenant-{tenant_id}"},
    )
    return tenant_id


def _insert_consultation(connection: sa.Connection, *, tenant_id: str) -> str:
    consultation_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO consultations (
                id, tenant_id, aggregate_revision, functional_identity_hash,
                buyer_legal_name, object_label, source_channel, source_received_at,
                lifecycle, freshness, metadata_history_json
            ) VALUES (
                :id, :tenant_id, 0, :identity_hash,
                'Acheteur test', 'Objet test', 'MANUAL', NOW(),
                'OPEN', 'UNKNOWN', CAST('[]' AS jsonb)
            )
            """
        ),
        {
            "id": consultation_id,
            "tenant_id": tenant_id,
            "identity_hash": uuid4().hex * 2,
        },
    )
    return consultation_id


def _insert_dce_version(
    connection: sa.Connection,
    *,
    tenant_id: str,
    consultation_id: str,
) -> str:
    dce_version_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO dce_versions (
                id, tenant_id, aggregate_revision, consultation_id, corpus_hash,
                provenance_channel, source_received_at, lifecycle, integrity,
                classification_readiness, analysis_readiness
            ) VALUES (
                :id, :tenant_id, 0, :consultation_id, :corpus_hash,
                'MANUAL', NOW(), 'ADMITTED', 'VERIFIED',
                'UNCLASSIFIED', 'NOT_READY'
            )
            """
        ),
        {
            "id": dce_version_id,
            "tenant_id": tenant_id,
            "consultation_id": consultation_id,
            "corpus_hash": uuid4().hex * 2,
        },
    )
    return dce_version_id


def _insert_case(
    connection: sa.Connection,
    *,
    tenant_id: str,
    functional_identity_hash: str,
    consultation_id: str | None,
    applicable_dce_version_id: str | None = None,
    lifecycle: str = "ACTIVE",
    business_origin: str = "MANUAL",
) -> str:
    case_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO cases (
                id, tenant_id, aggregate_revision, functional_identity_hash,
                title, object_description, business_origin, origin_rationale,
                consultation_id, scope_kind, scope_json, scope_fingerprint,
                applicable_dce_version_id, lifecycle, commercial_stage,
                decision_readiness, dce_freshness, responsibility_status
            ) VALUES (
                :id, :tenant_id, 0, :functional_identity_hash,
                'Lot gros œuvre', 'Réhabilitation test', :business_origin,
                'Création justifiée', :consultation_id, 'SINGLE_LOT',
                CAST('{"lot_numbers": ["01"]}' AS jsonb), :scope_fingerprint,
                :applicable_dce_version_id, :lifecycle, 'INTAKE',
                'NOT_ASSESSED', 'NO_DCE', 'UNASSIGNED'
            )
            """
        ),
        {
            "id": case_id,
            "tenant_id": tenant_id,
            "functional_identity_hash": functional_identity_hash,
            "business_origin": business_origin,
            "consultation_id": consultation_id,
            "scope_fingerprint": "a" * 64,
            "applicable_dce_version_id": applicable_dce_version_id,
            "lifecycle": lifecycle,
        },
    )
    return case_id


@pytest.mark.db
def test_migration_creates_case_and_history_tables(database_engine: sa.Engine) -> None:
    inspector = sa.inspect(database_engine)

    assert {
        "cases",
        "case_consultation_links",
        "case_dce_applicability_history",
    }.issubset(set(inspector.get_table_names()))


@pytest.mark.db
def test_case_reference_to_consultation_is_tenant_scoped(connection: sa.Connection) -> None:
    tenant_a = _insert_tenant(connection)
    tenant_b = _insert_tenant(connection)
    consultation_a = _insert_consultation(connection, tenant_id=tenant_a)

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_case(
            connection,
            tenant_id=tenant_b,
            functional_identity_hash="b" * 64,
            consultation_id=consultation_a,
        )


@pytest.mark.db
def test_case_reference_to_applicable_dce_is_tenant_scoped(connection: sa.Connection) -> None:
    tenant_a = _insert_tenant(connection)
    tenant_b = _insert_tenant(connection)
    consultation_a = _insert_consultation(connection, tenant_id=tenant_a)
    dce_a = _insert_dce_version(
        connection,
        tenant_id=tenant_a,
        consultation_id=consultation_a,
    )
    consultation_b = _insert_consultation(connection, tenant_id=tenant_b)

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_case(
            connection,
            tenant_id=tenant_b,
            functional_identity_hash="c" * 64,
            consultation_id=consultation_b,
            applicable_dce_version_id=dce_a,
        )


@pytest.mark.db
def test_only_one_non_archived_case_can_hold_functional_identity(
    connection: sa.Connection,
) -> None:
    tenant_id = _insert_tenant(connection)
    consultation_id = _insert_consultation(connection, tenant_id=tenant_id)
    identity_hash = "d" * 64
    first_case_id = _insert_case(
        connection,
        tenant_id=tenant_id,
        functional_identity_hash=identity_hash,
        consultation_id=consultation_id,
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_case(
            connection,
            tenant_id=tenant_id,
            functional_identity_hash=identity_hash,
            consultation_id=consultation_id,
        )

    connection.execute(
        sa.text(
            """
            UPDATE cases
            SET lifecycle = 'ARCHIVED', archived_reason = 'Doublon historique', archived_at = NOW()
            WHERE id = :case_id
            """
        ),
        {"case_id": first_case_id},
    )
    _insert_case(
        connection,
        tenant_id=tenant_id,
        functional_identity_hash=identity_hash,
        consultation_id=consultation_id,
    )


@pytest.mark.db
def test_case_without_consultation_is_allowed_only_for_manual_origin(
    connection: sa.Connection,
) -> None:
    tenant_id = _insert_tenant(connection)
    _insert_case(
        connection,
        tenant_id=tenant_id,
        functional_identity_hash="e" * 64,
        consultation_id=None,
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_case(
            connection,
            tenant_id=tenant_id,
            functional_identity_hash="f" * 64,
            consultation_id=None,
            business_origin="OPPORTUNITY",
        )


@pytest.mark.db
def test_case_history_allows_one_current_consultation_and_dce_link(
    connection: sa.Connection,
) -> None:
    tenant_id = _insert_tenant(connection)
    consultation_id = _insert_consultation(connection, tenant_id=tenant_id)
    dce_version_id = _insert_dce_version(
        connection,
        tenant_id=tenant_id,
        consultation_id=consultation_id,
    )
    case_id = _insert_case(
        connection,
        tenant_id=tenant_id,
        functional_identity_hash="0" * 64,
        consultation_id=consultation_id,
        applicable_dce_version_id=dce_version_id,
    )

    connection.execute(
        sa.text(
            """
            INSERT INTO case_consultation_links (
                id, tenant_id, case_id, consultation_id, scope_snapshot_json, is_current
            ) VALUES (
                :id, :tenant_id, :case_id, :consultation_id,
                CAST('{"kind": "SINGLE_LOT"}' AS jsonb), true
            )
            """
        ),
        {
            "id": str(uuid4()),
            "tenant_id": tenant_id,
            "case_id": case_id,
            "consultation_id": consultation_id,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO case_dce_applicability_history (
                id, tenant_id, case_id, dce_version_id, reason, is_current, set_at
            ) VALUES (
                :id, :tenant_id, :case_id, :dce_version_id, 'Initial DCE', true, NOW()
            )
            """
        ),
        {
            "id": str(uuid4()),
            "tenant_id": tenant_id,
            "case_id": case_id,
            "dce_version_id": dce_version_id,
        },
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                INSERT INTO case_consultation_links (
                    id, tenant_id, case_id, consultation_id, scope_snapshot_json, is_current
                ) VALUES (
                    :id, :tenant_id, :case_id, :consultation_id,
                    CAST('{"kind": "SINGLE_LOT"}' AS jsonb), true
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": tenant_id,
                "case_id": case_id,
                "consultation_id": consultation_id,
            },
        )

    connection.execute(
        sa.text(
            "UPDATE case_consultation_links SET is_current = false WHERE case_id = :case_id"
        ),
        {"case_id": case_id},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO case_consultation_links (
                id, tenant_id, case_id, consultation_id, scope_snapshot_json, is_current
            ) VALUES (
                :id, :tenant_id, :case_id, :consultation_id,
                CAST('{"kind": "SINGLE_LOT"}' AS jsonb), true
            )
            """
        ),
        {
            "id": str(uuid4()),
            "tenant_id": tenant_id,
            "case_id": case_id,
            "consultation_id": consultation_id,
        },
    )


@pytest.mark.db
def test_case_table_has_no_forbidden_owner_columns(database_engine: sa.Engine) -> None:
    columns = {column["name"] for column in sa.inspect(database_engine).get_columns("cases")}
    forbidden_owner_columns = {
        "price_id",
        "pricing_version_id",
        "decision_id",
        "task_id",
        "submission_id",
        "proof_id",
    }

    assert not (forbidden_owner_columns & columns)

from __future__ import annotations

import os
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
        sa.text(
            """
            INSERT INTO tenants (id, slug, lifecycle)
            VALUES (:id, :slug, 'ACTIVE')
            """
        ),
        {"id": tenant_id, "slug": f"tenant-{tenant_id}"},
    )
    return tenant_id


def _insert_consultation(
    connection: sa.Connection,
    *,
    tenant_id: str,
    functional_identity_hash: str,
) -> str:
    consultation_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO consultations (
                id, tenant_id, aggregate_revision, functional_identity_hash,
                buyer_legal_name, buyer_normalized_id, external_reference,
                object_label, source_channel, source_reference, source_received_at,
                lifecycle, freshness, metadata_history_json
            ) VALUES (
                :id, :tenant_id, 0, :functional_identity_hash,
                'CANSSM', 'FR-CANSSM', 'MA26NO0017',
                'Réhabilitation centre Filieris', 'MANUAL', 'test-source', NOW(),
                'OPEN', 'UNKNOWN', CAST('[]' AS jsonb)
            )
            """
        ),
        {
            "id": consultation_id,
            "tenant_id": tenant_id,
            "functional_identity_hash": functional_identity_hash,
        },
    )
    return consultation_id


def _insert_dce_version(
    connection: sa.Connection,
    *,
    tenant_id: str,
    consultation_id: str,
    corpus_hash: str,
) -> str:
    dce_version_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO dce_versions (
                id, tenant_id, aggregate_revision, consultation_id, corpus_hash,
                provenance_channel, provenance_reference, source_received_at,
                lifecycle, integrity, classification_readiness, analysis_readiness
            ) VALUES (
                :id, :tenant_id, 0, :consultation_id, :corpus_hash,
                'MANUAL', 'DCE-ORIGINAL', NOW(),
                'ADMITTED', 'VERIFIED', 'UNCLASSIFIED', 'NOT_READY'
            )
            """
        ),
        {
            "id": dce_version_id,
            "tenant_id": tenant_id,
            "consultation_id": consultation_id,
            "corpus_hash": corpus_hash,
        },
    )
    return dce_version_id


@pytest.mark.db
def test_migration_creates_consultation_and_dce_tables(database_engine: sa.Engine) -> None:
    inspector = sa.inspect(database_engine)

    assert {
        "consultations",
        "consultation_lots",
        "consultation_tranches",
        "dce_versions",
        "dce_documents",
        "dce_document_classifications",
        "dce_document_issues",
        "dce_missing_document_declarations",
        "dce_source_statements",
    }.issubset(set(inspector.get_table_names()))


@pytest.mark.db
def test_consultation_functional_identity_is_unique_within_tenant(
    connection: sa.Connection,
) -> None:
    tenant_id = _insert_tenant(connection)
    identity_hash = "a" * 64
    _insert_consultation(
        connection,
        tenant_id=tenant_id,
        functional_identity_hash=identity_hash,
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_consultation(
            connection,
            tenant_id=tenant_id,
            functional_identity_hash=identity_hash,
        )


@pytest.mark.db
def test_consultation_identity_can_exist_in_another_tenant(connection: sa.Connection) -> None:
    identity_hash = "b" * 64
    first_tenant = _insert_tenant(connection)
    second_tenant = _insert_tenant(connection)

    _insert_consultation(
        connection,
        tenant_id=first_tenant,
        functional_identity_hash=identity_hash,
    )
    _insert_consultation(
        connection,
        tenant_id=second_tenant,
        functional_identity_hash=identity_hash,
    )

    count = connection.scalar(
        sa.text(
            "SELECT count(*) FROM consultations WHERE functional_identity_hash = :identity_hash"
        ),
        {"identity_hash": identity_hash},
    )
    assert count == 2


@pytest.mark.db
def test_dce_version_cannot_reference_consultation_from_another_tenant(
    connection: sa.Connection,
) -> None:
    tenant_a = _insert_tenant(connection)
    tenant_b = _insert_tenant(connection)
    consultation_a = _insert_consultation(
        connection,
        tenant_id=tenant_a,
        functional_identity_hash="c" * 64,
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_dce_version(
            connection,
            tenant_id=tenant_b,
            consultation_id=consultation_a,
            corpus_hash="d" * 64,
        )


@pytest.mark.db
def test_dce_corpus_hash_is_immutable_but_lifecycle_can_change(connection: sa.Connection) -> None:
    tenant_id = _insert_tenant(connection)
    consultation_id = _insert_consultation(
        connection,
        tenant_id=tenant_id,
        functional_identity_hash="e" * 64,
    )
    dce_version_id = _insert_dce_version(
        connection,
        tenant_id=tenant_id,
        consultation_id=consultation_id,
        corpus_hash="f" * 64,
    )

    with pytest.raises(sa.exc.ProgrammingError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                UPDATE dce_versions
                SET corpus_hash = :new_hash
                WHERE id = :dce_version_id AND tenant_id = :tenant_id
                """
            ),
            {
                "new_hash": "0" * 64,
                "dce_version_id": dce_version_id,
                "tenant_id": tenant_id,
            },
        )

    connection.execute(
        sa.text(
            """
            UPDATE dce_versions
            SET lifecycle = 'SUPERSEDED', superseded_at = NOW()
            WHERE id = :dce_version_id AND tenant_id = :tenant_id
            """
        ),
        {"dce_version_id": dce_version_id, "tenant_id": tenant_id},
    )
    lifecycle = connection.scalar(
        sa.text("SELECT lifecycle FROM dce_versions WHERE id = :dce_version_id"),
        {"dce_version_id": dce_version_id},
    )
    assert lifecycle == "SUPERSEDED"


@pytest.mark.db
def test_dce_document_original_fields_are_immutable(connection: sa.Connection) -> None:
    tenant_id = _insert_tenant(connection)
    consultation_id = _insert_consultation(
        connection,
        tenant_id=tenant_id,
        functional_identity_hash="1" * 64,
    )
    dce_version_id = _insert_dce_version(
        connection,
        tenant_id=tenant_id,
        consultation_id=consultation_id,
        corpus_hash="2" * 64,
    )
    document_id = str(uuid4())
    storage_object_id = str(uuid4())
    document_hash = "3" * 64
    connection.execute(
        sa.text(
            """
            INSERT INTO dce_staged_objects (
                id, tenant_id, consultation_id, storage_key, original_filename,
                expected_byte_size, actual_byte_size, sha256, media_type, source_channel,
                state, scan_verdict, scanner_name, scanner_signature_version, scanned_at,
                expires_at, consumed_by_dce_version_id, consumed_at
            ) VALUES (
                :storage_object_id, :tenant_id, :consultation_id, 'dce-staging/rc.pdf',
                'RC.pdf', 1234, 1234, :sha256, 'application/pdf', 'BUYER_PLATFORM',
                'CONSUMED', 'CLEAN', 'test-scanner', 'test-signatures', NOW(),
                NOW() + INTERVAL '1 day', :dce_version_id, NOW()
            )
            """
        ),
        {
            "storage_object_id": storage_object_id,
            "tenant_id": tenant_id,
            "consultation_id": consultation_id,
            "dce_version_id": dce_version_id,
            "sha256": document_hash,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO dce_documents (
                id, tenant_id, dce_version_id, storage_object_id, storage_key,
                original_filename, media_type, byte_size, sha256, received_from
            ) VALUES (
                :id, :tenant_id, :dce_version_id, :storage_object_id, 'dce/rc.pdf',
                'RC.pdf', 'application/pdf', 1234, :sha256, 'buyer-platform'
            )
            """
        ),
        {
            "id": document_id,
            "tenant_id": tenant_id,
            "dce_version_id": dce_version_id,
            "storage_object_id": storage_object_id,
            "sha256": document_hash,
        },
    )

    with pytest.raises(sa.exc.ProgrammingError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                UPDATE dce_documents
                SET original_filename = 'RC-corrige.pdf'
                WHERE id = :document_id AND tenant_id = :tenant_id
                """
            ),
            {"document_id": document_id, "tenant_id": tenant_id},
        )


@pytest.mark.db
def test_same_dce_corpus_cannot_be_registered_twice_for_one_consultation(
    connection: sa.Connection,
) -> None:
    tenant_id = _insert_tenant(connection)
    consultation_id = _insert_consultation(
        connection,
        tenant_id=tenant_id,
        functional_identity_hash="4" * 64,
    )
    _insert_dce_version(
        connection,
        tenant_id=tenant_id,
        consultation_id=consultation_id,
        corpus_hash="5" * 64,
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_dce_version(
            connection,
            tenant_id=tenant_id,
            consultation_id=consultation_id,
            corpus_hash="5" * 64,
        )

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.modules.case.infrastructure.repositories import SqlAlchemyCaseRepository
from app.modules.dce.infrastructure.repositories import (
    SqlAlchemyConsultationRepository,
    SqlAlchemyDceVersionRepository,
)
from app.modules.decision.infrastructure.repositories import SqlAlchemyDecisionRepository
from app.platform.persistence.repository import OptimisticRevisionConflictError
from sqlalchemy.orm import Session

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


@pytest.fixture
def session(connection: sa.Connection):
    repository_session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield repository_session
    finally:
        repository_session.close()


def _insert_tenant(connection: sa.Connection) -> str:
    tenant_id = str(uuid4())
    connection.execute(
        sa.text(
            "INSERT INTO tenants (id, slug, lifecycle) VALUES (:id, :slug, 'ACTIVE')"
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
                'Acheteur test', 'Réhabilitation école', 'MANUAL', NOW(),
                'OPEN', 'UNKNOWN', CAST('[]' AS jsonb)
            )
            """
        ),
        {"id": consultation_id, "tenant_id": tenant_id, "identity_hash": uuid4().hex * 2},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO consultation_lots (id, tenant_id, consultation_id, lot_number, label)
            VALUES (:id, :tenant_id, :consultation_id, '01', 'Gros œuvre')
            """
        ),
        {"id": str(uuid4()), "tenant_id": tenant_id, "consultation_id": consultation_id},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO consultation_tranches (
                id, tenant_id, consultation_id, tranche_reference, tranche_kind
            ) VALUES (:id, :tenant_id, :consultation_id, 'TF', 'FERME')
            """
        ),
        {"id": str(uuid4()), "tenant_id": tenant_id, "consultation_id": consultation_id},
    )
    return consultation_id


def _insert_dce_version(
    connection: sa.Connection,
    *,
    tenant_id: str,
    consultation_id: str,
) -> tuple[str, str]:
    dce_version_id = str(uuid4())
    document_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO dce_versions (
                id, tenant_id, aggregate_revision, consultation_id, corpus_hash,
                provenance_channel, source_received_at, lifecycle, integrity,
                classification_readiness, analysis_readiness
            ) VALUES (
                :id, :tenant_id, 0, :consultation_id, :corpus_hash,
                'MANUAL', NOW(), 'ADMITTED', 'VERIFIED', 'UNCLASSIFIED', 'NOT_READY'
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
    connection.execute(
        sa.text(
            """
            INSERT INTO dce_documents (
                id, tenant_id, dce_version_id, storage_object_id, storage_key,
                original_filename, media_type, byte_size, sha256, received_from
            ) VALUES (
                :id, :tenant_id, :dce_version_id, :storage_object_id, 'dce/rc.pdf',
                'rc.pdf', 'application/pdf', 42, :sha256, 'Acheteur'
            )
            """
        ),
        {
            "id": document_id,
            "tenant_id": tenant_id,
            "dce_version_id": dce_version_id,
            "storage_object_id": str(uuid4()),
            "sha256": uuid4().hex * 2,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO dce_source_statements (
                id, tenant_id, dce_version_id, dce_document_id, locator_json, excerpt,
                extraction_origin
            ) VALUES (
                :id, :tenant_id, :dce_version_id, :dce_document_id,
                CAST('{"page": 1}' AS jsonb), 'Extrait source', 'MANUAL'
            )
            """
        ),
        {
            "id": str(uuid4()),
            "tenant_id": tenant_id,
            "dce_version_id": dce_version_id,
            "dce_document_id": document_id,
        },
    )
    return dce_version_id, document_id


def _insert_case(
    connection: sa.Connection,
    *,
    tenant_id: str,
    consultation_id: str,
    dce_version_id: str,
) -> str:
    case_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO cases (
                id, tenant_id, aggregate_revision, functional_identity_hash, title,
                object_description, business_origin, origin_rationale, consultation_id,
                scope_kind, scope_json, scope_fingerprint, applicable_dce_version_id,
                lifecycle, commercial_stage, decision_readiness, dce_freshness,
                responsibility_status
            ) VALUES (
                :id, :tenant_id, 0, :identity_hash, 'Lot gros œuvre', 'Affaire test',
                'MANUAL', 'Création test', :consultation_id, 'SINGLE_LOT',
                CAST('{"lot_numbers": ["01"]}' AS jsonb), :scope_fingerprint,
                :dce_version_id, 'ACTIVE', 'AWAITING_DECISION', 'READY', 'CURRENT',
                'UNASSIGNED'
            )
            """
        ),
        {
            "id": case_id,
            "tenant_id": tenant_id,
            "identity_hash": uuid4().hex * 2,
            "consultation_id": consultation_id,
            "scope_fingerprint": uuid4().hex * 2,
            "dce_version_id": dce_version_id,
        },
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
                :id, :tenant_id, :case_id, :dce_version_id, 'DCE de référence', true, NOW()
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
    return case_id


def _insert_decision(connection: sa.Connection, *, tenant_id: str, case_id: str) -> str:
    decision_id = str(uuid4())
    context_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO decisions (
                id, tenant_id, aggregate_revision, decision_type, subject_type, subject_id,
                case_id, scope_fingerprint, decision_key_hash, cycle_number, lifecycle,
                outcome, validity, condition_status, context_status
            ) VALUES (
                :id, :tenant_id, 0, 'GO_NO_GO', 'CASE', :case_id, :case_id,
                :scope_fingerprint, :decision_key_hash, 1, 'DRAFT', 'UNDECIDED', 'CURRENT',
                'NOT_APPLICABLE', 'INCOMPLETE'
            )
            """
        ),
        {
            "id": decision_id,
            "tenant_id": tenant_id,
            "case_id": case_id,
            "scope_fingerprint": uuid4().hex * 2,
            "decision_key_hash": uuid4().hex * 2,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO decision_contexts (
                id, tenant_id, decision_id, sequence_number, context_fingerprint,
                canonical_context_json, rationale, unknowns_json, prepared_at, context_state,
                is_selected_final
            ) VALUES (
                :id, :tenant_id, :decision_id, 1, :context_fingerprint,
                CAST('{"references": ["case:test"]}' AS jsonb), 'Contexte',
                CAST('[]' AS jsonb), NOW(), 'FROZEN', false
            )
            """
        ),
        {
            "id": context_id,
            "tenant_id": tenant_id,
            "decision_id": decision_id,
            "context_fingerprint": uuid4().hex * 2,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO decision_context_references (
                id, tenant_id, decision_context_id, aggregate_type, aggregate_id,
                aggregate_revision, reference_role
            ) VALUES (
                :id, :tenant_id, :context_id, 'CASE', :case_id, 0, 'SUBJECT'
            )
            """
        ),
        {
            "id": str(uuid4()),
            "tenant_id": tenant_id,
            "context_id": context_id,
            "case_id": case_id,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO decision_conditions (
                id, tenant_id, decision_id, label, owner_actor_id, due_at,
                failure_consequence, status
            ) VALUES (
                :id, :tenant_id, :decision_id, 'Attestation', :owner_actor_id, NOW(),
                'Bloquer la réponse', 'OPEN'
            )
            """
        ),
        {
            "id": str(uuid4()),
            "tenant_id": tenant_id,
            "decision_id": decision_id,
            "owner_actor_id": str(uuid4()),
        },
    )
    return decision_id


@pytest.fixture
def aggregate_ids(connection: sa.Connection) -> tuple[str, str, str, str, str]:
    tenant_id = _insert_tenant(connection)
    consultation_id = _insert_consultation(connection, tenant_id=tenant_id)
    dce_version_id, _ = _insert_dce_version(
        connection,
        tenant_id=tenant_id,
        consultation_id=consultation_id,
    )
    case_id = _insert_case(
        connection,
        tenant_id=tenant_id,
        consultation_id=consultation_id,
        dce_version_id=dce_version_id,
    )
    decision_id = _insert_decision(connection, tenant_id=tenant_id, case_id=case_id)
    return tenant_id, consultation_id, dce_version_id, case_id, decision_id


@pytest.mark.db
def test_repositories_filter_roots_by_tenant(
    connection: sa.Connection,
    session: Session,
    aggregate_ids: tuple[str, str, str, str, str],
) -> None:
    tenant_id, consultation_id, dce_version_id, case_id, decision_id = aggregate_ids
    other_tenant_id = _insert_tenant(connection)

    repositories_and_ids = (
        (SqlAlchemyConsultationRepository(session), consultation_id),
        (SqlAlchemyDceVersionRepository(session), dce_version_id),
        (SqlAlchemyCaseRepository(session), case_id),
        (SqlAlchemyDecisionRepository(session), decision_id),
    )

    for repository, aggregate_id in repositories_and_ids:
        assert repository.get(tenant_id=other_tenant_id, aggregate_id=aggregate_id) is None
        assert repository.get(tenant_id=tenant_id, aggregate_id=aggregate_id) is not None


@pytest.mark.db
def test_case_repository_loads_only_case_owned_histories(
    session: Session,
    aggregate_ids: tuple[str, str, str, str, str],
) -> None:
    tenant_id, _, _, case_id, _ = aggregate_ids

    snapshot = SqlAlchemyCaseRepository(session).get(tenant_id=tenant_id, aggregate_id=case_id)

    assert snapshot is not None
    assert str(snapshot.root.id) == case_id
    assert len(snapshot.consultation_links) == 1
    assert len(snapshot.dce_applicability_history) == 1


@pytest.mark.db
def test_consultation_and_dce_repositories_load_their_owned_children(
    session: Session,
    aggregate_ids: tuple[str, str, str, str, str],
) -> None:
    tenant_id, consultation_id, dce_version_id, _, _ = aggregate_ids

    consultation = SqlAlchemyConsultationRepository(session).get(
        tenant_id=tenant_id,
        aggregate_id=consultation_id,
    )
    dce_version = SqlAlchemyDceVersionRepository(session).get(
        tenant_id=tenant_id,
        aggregate_id=dce_version_id,
    )

    assert consultation is not None
    assert len(consultation.lots) == 1
    assert len(consultation.tranches) == 1
    assert dce_version is not None
    assert len(dce_version.documents) == 1
    assert len(dce_version.source_statements) == 1


@pytest.mark.db
def test_decision_repository_loads_contexts_references_and_conditions(
    session: Session,
    aggregate_ids: tuple[str, str, str, str, str],
) -> None:
    tenant_id, _, _, _, decision_id = aggregate_ids

    snapshot = SqlAlchemyDecisionRepository(session).get(
        tenant_id=tenant_id,
        aggregate_id=decision_id,
    )

    assert snapshot is not None
    assert len(snapshot.contexts) == 1
    assert len(snapshot.context_references) == 1
    assert len(snapshot.conditions) == 1


RepositoryFactory = Callable[[Session], object]


@pytest.mark.db
@pytest.mark.parametrize(
    ("repository_factory", "aggregate_index", "changes"),
    [
        (SqlAlchemyConsultationRepository, 1, {"freshness": "CURRENT"}),
        (SqlAlchemyDceVersionRepository, 2, {"analysis_readiness": "READY_FOR_ANALYSIS"}),
        (SqlAlchemyCaseRepository, 3, {"commercial_stage": "ANALYSIS"}),
        (SqlAlchemyDecisionRepository, 4, {"context_status": "FROZEN"}),
    ],
)
def test_repository_update_requires_exact_expected_revision(
    session: Session,
    aggregate_ids: tuple[str, str, str, str, str],
    repository_factory: RepositoryFactory,
    aggregate_index: int,
    changes: dict[str, object],
) -> None:
    tenant_id = aggregate_ids[0]
    aggregate_id = aggregate_ids[aggregate_index]
    repository = repository_factory(session)

    assert repository.update_root(
        tenant_id=tenant_id,
        aggregate_id=aggregate_id,
        expected_revision=0,
        changes=changes,
    ) == 1

    with pytest.raises(OptimisticRevisionConflictError):
        repository.update_root(
            tenant_id=tenant_id,
            aggregate_id=aggregate_id,
            expected_revision=0,
            changes=changes,
        )

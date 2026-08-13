from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import DatabaseError, IntegrityError

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


def _insert_case(connection: sa.Connection, *, tenant_id: str) -> str:
    case_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO cases (
                id, tenant_id, aggregate_revision, functional_identity_hash,
                title, business_origin, origin_rationale, scope_kind, scope_json,
                scope_fingerprint, lifecycle, commercial_stage, decision_readiness,
                dce_freshness, responsibility_status
            ) VALUES (
                :id, :tenant_id, 0, :functional_identity_hash,
                'Affaire de test', 'MANUAL', 'Création de test', 'SINGLE_LOT',
                CAST('{"lot_numbers": ["01"]}' AS jsonb), :scope_fingerprint,
                'ACTIVE', 'AWAITING_DECISION', 'READY', 'CURRENT', 'UNASSIGNED'
            )
            """
        ),
        {
            "id": case_id,
            "tenant_id": tenant_id,
            "functional_identity_hash": uuid4().hex * 2,
            "scope_fingerprint": "a" * 64,
        },
    )
    return case_id


def _insert_decision(
    connection: sa.Connection,
    *,
    tenant_id: str,
    case_id: str,
    decision_key_hash: str | None = None,
    cycle_number: int = 1,
) -> str:
    decision_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO decisions (
                id, tenant_id, aggregate_revision, decision_type, subject_type, subject_id,
                case_id, scope_fingerprint, decision_key_hash, cycle_number, lifecycle,
                outcome, validity, condition_status, context_status
            ) VALUES (
                :id, :tenant_id, 0, 'GO_NO_GO', 'CASE', :case_id,
                :case_id, :scope_fingerprint, :decision_key_hash, :cycle_number, 'DRAFT',
                'UNDECIDED', 'CURRENT', 'NOT_APPLICABLE', 'INCOMPLETE'
            )
            """
        ),
        {
            "id": decision_id,
            "tenant_id": tenant_id,
            "case_id": case_id,
            "scope_fingerprint": "b" * 64,
            "decision_key_hash": decision_key_hash or uuid4().hex * 2,
            "cycle_number": cycle_number,
        },
    )
    return decision_id


def _insert_context(
    connection: sa.Connection,
    *,
    tenant_id: str,
    decision_id: str,
    sequence_number: int = 1,
    selected_final: bool = False,
) -> str:
    context_id = str(uuid4())
    connection.execute(
        sa.text(
            """
            INSERT INTO decision_contexts (
                id, tenant_id, decision_id, sequence_number, context_fingerprint,
                canonical_context_json, rationale, unknowns_json, prepared_at,
                context_state, is_selected_final
            ) VALUES (
                :id, :tenant_id, :decision_id, :sequence_number, :context_fingerprint,
                CAST('{"references": ["case:test"], "risks": []}' AS jsonb),
                'Contexte de test', CAST('[]' AS jsonb), NOW(), 'FROZEN', :selected_final
            )
            """
        ),
        {
            "id": context_id,
            "tenant_id": tenant_id,
            "decision_id": decision_id,
            "sequence_number": sequence_number,
            "context_fingerprint": uuid4().hex * 2,
            "selected_final": selected_final,
        },
    )
    return context_id


@pytest.mark.db
def test_migration_creates_decision_and_owned_history_tables(database_engine: sa.Engine) -> None:
    inspector = sa.inspect(database_engine)

    assert {
        "decisions",
        "decision_contexts",
        "decision_context_references",
        "decision_conditions",
    }.issubset(set(inspector.get_table_names()))


@pytest.mark.db
def test_decision_case_reference_is_tenant_scoped(connection: sa.Connection) -> None:
    tenant_a = _insert_tenant(connection)
    tenant_b = _insert_tenant(connection)
    case_a = _insert_case(connection, tenant_id=tenant_a)

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_decision(connection, tenant_id=tenant_b, case_id=case_a)


@pytest.mark.db
def test_decision_key_cycle_is_unique_per_tenant(connection: sa.Connection) -> None:
    tenant_id = _insert_tenant(connection)
    case_id = _insert_case(connection, tenant_id=tenant_id)
    decision_key_hash = "c" * 64
    _insert_decision(
        connection,
        tenant_id=tenant_id,
        case_id=case_id,
        decision_key_hash=decision_key_hash,
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_decision(
            connection,
            tenant_id=tenant_id,
            case_id=case_id,
            decision_key_hash=decision_key_hash,
        )


@pytest.mark.db
def test_finalized_decision_requires_its_selected_frozen_context(connection: sa.Connection) -> None:
    tenant_id = _insert_tenant(connection)
    case_id = _insert_case(connection, tenant_id=tenant_id)
    decision_id = _insert_decision(connection, tenant_id=tenant_id, case_id=case_id)
    context_id = _insert_context(
        connection,
        tenant_id=tenant_id,
        decision_id=decision_id,
        selected_final=True,
    )

    connection.execute(
        sa.text(
            """
            UPDATE decisions
            SET lifecycle = 'FINALIZED', outcome = 'GO', selected_final_context_id = :context_id,
                final_justification = 'Décision patron validée',
                finalized_by_actor_id = :actor_id, finalized_at = NOW(), context_status = 'FROZEN'
            WHERE id = :decision_id
            """
        ),
        {"decision_id": decision_id, "context_id": context_id, "actor_id": str(uuid4())},
    )

    other_decision_id = _insert_decision(connection, tenant_id=tenant_id, case_id=case_id)
    other_context_id = _insert_context(
        connection,
        tenant_id=tenant_id,
        decision_id=other_decision_id,
    )
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                UPDATE decisions
                SET lifecycle = 'FINALIZED',
                    outcome = 'GO',
                    selected_final_context_id = :context_id,
                    final_justification = 'Contexte d une autre décision',
                    finalized_by_actor_id = :actor_id,
                    finalized_at = NOW(),
                    context_status = 'FROZEN'
                WHERE id = :decision_id
                """
            ),
            {
                "decision_id": decision_id,
                "context_id": other_context_id,
                "actor_id": str(uuid4()),
            },
        )


@pytest.mark.db
def test_only_one_context_can_be_selected_final_per_decision(connection: sa.Connection) -> None:
    tenant_id = _insert_tenant(connection)
    case_id = _insert_case(connection, tenant_id=tenant_id)
    decision_id = _insert_decision(connection, tenant_id=tenant_id, case_id=case_id)
    _insert_context(
        connection,
        tenant_id=tenant_id,
        decision_id=decision_id,
        selected_final=True,
    )

    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_context(
            connection,
            tenant_id=tenant_id,
            decision_id=decision_id,
            sequence_number=2,
            selected_final=True,
        )


@pytest.mark.db
def test_frozen_decision_context_content_is_immutable(connection: sa.Connection) -> None:
    tenant_id = _insert_tenant(connection)
    case_id = _insert_case(connection, tenant_id=tenant_id)
    decision_id = _insert_decision(connection, tenant_id=tenant_id, case_id=case_id)
    context_id = _insert_context(connection, tenant_id=tenant_id, decision_id=decision_id)

    with pytest.raises(DatabaseError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                UPDATE decision_contexts
                SET rationale = 'Réécriture interdite du contexte figé'
                WHERE id = :context_id
                """
            ),
            {"context_id": context_id},
        )


@pytest.mark.db
def test_decision_condition_requires_deadline_or_reason_and_consequence(
    connection: sa.Connection,
) -> None:
    tenant_id = _insert_tenant(connection)
    case_id = _insert_case(connection, tenant_id=tenant_id)
    decision_id = _insert_decision(connection, tenant_id=tenant_id, case_id=case_id)

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                INSERT INTO decision_conditions (
                    id, tenant_id, decision_id, label, owner_actor_id, failure_consequence, status
                ) VALUES (
                    :id, :tenant_id, :decision_id, 'Attestation manquante', :owner_actor_id,
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

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                INSERT INTO decision_conditions (
                    id, tenant_id, decision_id, label, owner_actor_id, due_date_absence_reason,
                    failure_consequence, status
                ) VALUES (
                    :id, :tenant_id, :decision_id, 'Attestation manquante', :owner_actor_id,
                    'Échéance absente du RC', '   ', 'OPEN'
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


@pytest.mark.db
def test_decision_table_contains_no_financial_or_forbidden_cross_root_columns(
    database_engine: sa.Engine,
) -> None:
    columns = {column["name"] for column in sa.inspect(database_engine).get_columns("decisions")}
    forbidden_owner_columns = {
        "price_id",
        "pricing_version_id",
        "submission_id",
        "task_id",
        "proof_id",
    }
    forbidden_financial_terms = {"price", "cost", "margin", "quote", "treasury"}

    assert not (forbidden_owner_columns & columns)
    assert not any(
        term in column_name for term in forbidden_financial_terms for column_name in columns
    )

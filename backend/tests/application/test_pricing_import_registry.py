from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.platform.security.models import PricingImportBatchRecord, PricingImportRowRecord
from sqlalchemy.exc import IntegrityError, ProgrammingError

from tests.application.test_financial_report_draft_lines import _seed_draft


def _batch(*, actor, case_id):
    return PricingImportBatchRecord(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        case_id=case_id,
        document_kind="DPGF",
        source_sha256="a" * 64,
        state="PREVIEWED",
        aggregate_revision=1,
        row_count=1,
        valid_row_count=1,
        error_count=0,
        total_minor=12500,
        actor_id=actor.actor_id,
        membership_id=actor.membership_id,
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=actor.correlation_id,
    )


def _row(*, actor, batch_id, row_number=2):
    return PricingImportRowRecord(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        batch_id=batch_id,
        row_number=row_number,
        code="A-01",
        designation="Terrassement",
        unit="m2",
        quantity_decimal="10",
        unit_price_minor=1250,
        total_minor=12500,
        error_codes_json=[],
    )


def test_pricing_import_registry_persists_normalized_batch_and_row(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    batch = _batch(actor=actor, case_id=case_id)
    row = _row(actor=actor, batch_id=batch.id)
    with session_factory.begin() as session:
        session.add(batch)
        session.add(row)

    with session_factory() as session:
        stored_batch = session.get(PricingImportBatchRecord, batch.id)
        stored_row = session.get(PricingImportRowRecord, row.id)
    assert stored_batch is not None
    assert stored_batch.state == "PREVIEWED"
    assert stored_batch.total_minor == 12500
    assert stored_row is not None
    assert stored_row.error_codes_json == []


def test_pricing_import_registry_is_append_only_and_unique(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    batch = _batch(actor=actor, case_id=case_id)
    row = _row(actor=actor, batch_id=batch.id)
    with session_factory.begin() as session:
        session.add(batch)
        session.add(row)

    with pytest.raises(ProgrammingError), session_factory.begin() as session:
        session.execute(
            sa.update(PricingImportBatchRecord)
            .where(PricingImportBatchRecord.id == batch.id)
            .values(state="COMMITTED")
        )

    with pytest.raises(ProgrammingError), session_factory.begin() as session:
        session.execute(
            sa.delete(PricingImportRowRecord).where(PricingImportRowRecord.id == row.id)
        )

    duplicate = _row(actor=actor, batch_id=batch.id)
    with pytest.raises(IntegrityError), session_factory.begin() as session:
        session.add(duplicate)


def test_pricing_import_registry_rejects_invalid_source_and_bounds(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    invalid = _batch(actor=actor, case_id=case_id)
    invalid.source_sha256 = "not-a-hash"
    with pytest.raises(IntegrityError), session_factory.begin() as session:
        session.add(invalid)

    invalid_rows = _batch(actor=actor, case_id=case_id)
    invalid_rows.valid_row_count = 2
    with pytest.raises(IntegrityError), session_factory.begin() as session:
        session.add(invalid_rows)

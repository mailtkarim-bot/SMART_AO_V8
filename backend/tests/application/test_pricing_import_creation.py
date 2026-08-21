from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.modules.pricing.application.import_commands import (
    CreatePricingImportPreviewCommand,
    CreatePricingImportRowCommand,
)
from app.modules.pricing.application.import_creation import (
    PricingImportCreationService,
    pricing_import_creation_handlers,
)
from app.platform.events.dispatcher import CommandDispatcher, IdempotencyKeyReusedError
from app.platform.persistence.models import (
    CommandReceiptRecord,
    DomainEventRecord,
    OutboxMessageRecord,
)
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.context import ActorKind
from app.platform.security.models import (
    PricingImportBatchRecord,
    PricingImportRowRecord,
)
from pydantic import ValidationError

from tests.application.test_financial_report_draft_lines import _seed_draft

NOW = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)


def _command(case_id, *, command_id=None, idempotency_key=None, rows=None):
    return CreatePricingImportPreviewCommand(
        command_id=command_id or uuid4(),
        idempotency_key=idempotency_key or uuid4(),
        correlation_id=uuid4(),
        case_id=case_id,
        document_kind="DPGF",
        source_sha256="c" * 64,
        rows=rows or [
            CreatePricingImportRowCommand(
                row_number=2,
                code="A-01",
                designation="Terrassement",
                unit="m2",
                quantity_decimal="10",
                unit_price_minor=1250,
                total_minor=12500,
            ),
            CreatePricingImportRowCommand(
                row_number=3,
                code="A-02",
                designation="Fondations",
                unit="m3",
                quantity_decimal="2",
                unit_price_minor=10000,
                total_minor=20000,
            ),
        ],
    )


def _service(session_factory):
    return PricingImportCreationService(
        session_factory=session_factory,
        dispatcher=CommandDispatcher(
            session_factory=session_factory,
            handlers=pricing_import_creation_handlers(),
        ),
        policy=AuthorizationPolicy(),
    )


def test_creation_persists_preview_batch_rows_and_non_financial_event(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)

    command = _command(case_id)
    result = _service(session_factory).create(
        actor=actor,
        command=command,
        now=NOW,
    )

    with session_factory() as session:
        batch = session.scalar(
            sa.select(PricingImportBatchRecord).where(
                PricingImportBatchRecord.tenant_id == actor.tenant_id,
                PricingImportBatchRecord.command_id == command.command_id,
            )
        )
        rows = session.scalars(
            sa.select(PricingImportRowRecord)
            .where(PricingImportRowRecord.tenant_id == actor.tenant_id)
            .order_by(PricingImportRowRecord.row_number)
        ).all()
        event = session.scalar(
            sa.select(DomainEventRecord).where(DomainEventRecord.aggregate_id == batch.id)
        )
        outbox = session.scalar(
            sa.select(OutboxMessageRecord).where(OutboxMessageRecord.event_id == event.id)
        )
    assert result.result_code == "PRICING_IMPORT_PREVIEWED"
    assert batch is not None
    assert batch.state == "PREVIEWED"
    assert batch.tenant_id == actor.tenant_id
    assert batch.case_id == case_id
    assert batch.row_count == 2
    assert batch.valid_row_count == 2
    assert batch.error_count == 0
    assert batch.total_minor == 32500
    assert len(rows) == 2
    assert event is not None
    assert event.event_type == "PricingImportPreviewed"
    assert "total_minor" not in event.payload_json["data"]
    assert "source_sha256" not in event.payload_json["data"]
    assert outbox is not None


def test_creation_replays_same_idempotency_key_without_duplicate_rows(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    command = _command(case_id)
    service = _service(session_factory)

    first = service.create(actor=actor, command=command, now=NOW)
    replay = service.create(actor=actor, command=command, now=NOW)

    with session_factory() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(PricingImportBatchRecord)
                .where(PricingImportBatchRecord.tenant_id == actor.tenant_id)
            )
            == 1
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(PricingImportRowRecord)
                .where(PricingImportRowRecord.tenant_id == actor.tenant_id)
            )
            == 2
        )
        receipt = session.scalar(
            sa.select(CommandReceiptRecord).where(
                CommandReceiptRecord.tenant_id == actor.tenant_id,
                CommandReceiptRecord.idempotency_key == command.idempotency_key,
            )
        )
    assert first.replayed is False
    assert replay.replayed is True
    assert replay.event_ids == first.event_ids
    assert receipt is not None
    assert receipt.status == "SUCCEEDED"


def test_creation_rejects_idempotency_key_reuse_with_different_request(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    key = uuid4()
    service = _service(session_factory)
    service.create(actor=actor, command=_command(case_id, idempotency_key=key), now=NOW)

    changed = _command(
        case_id,
        idempotency_key=key,
        rows=[
            CreatePricingImportRowCommand(
                row_number=2,
                designation="Changed",
                quantity_decimal="1",
                total_minor=1,
            )
        ],
    )
    with pytest.raises(IdempotencyKeyReusedError):
        service.create(actor=actor, command=changed, now=NOW)


def test_creation_persists_invalid_rows_as_preview_errors_but_never_applies_them(
    session_factory,
):
    actor, case_id, _, _ = _seed_draft(session_factory)
    invalid = CreatePricingImportRowCommand(
        row_number=2,
        designation=None,
        quantity_decimal=None,
        total_minor=None,
        errors=["DESIGNATION_REQUIRED", "PRICE_REQUIRED"],
    )

    command = _command(case_id, rows=[invalid])
    _service(session_factory).create(actor=actor, command=command, now=NOW)

    with session_factory() as session:
        batch = session.scalar(
            sa.select(PricingImportBatchRecord).where(
                PricingImportBatchRecord.tenant_id == actor.tenant_id,
                PricingImportBatchRecord.command_id == command.command_id,
            )
        )
        row = session.scalar(
            sa.select(PricingImportRowRecord).where(
                PricingImportRowRecord.tenant_id == actor.tenant_id,
                PricingImportRowRecord.batch_id == batch.id,
            )
        )
    assert batch is not None
    assert batch.state == "PREVIEWED"
    assert batch.valid_row_count == 0
    assert batch.error_count == 2
    assert row is not None
    assert row.error_codes_json == ["DESIGNATION_REQUIRED", "PRICE_REQUIRED"]


def test_creation_refuses_collaborator_before_case_resolution(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    collaborator = replace(actor, actor_kind=ActorKind.COLLABORATEUR)

    with pytest.raises(PermissionError, match="PRICING_IMPORT_PATRON_REQUIRED"):
        _service(session_factory).create(actor=collaborator, command=_command(case_id), now=NOW)

    with session_factory() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(PricingImportBatchRecord)
                .where(PricingImportBatchRecord.tenant_id == actor.tenant_id)
            )
            == 0
        )


def test_creation_refuses_case_from_another_tenant(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    other_actor, _, _, _ = _seed_draft(session_factory)

    with pytest.raises(PermissionError, match="NOT_FOUND_OR_FORBIDDEN"):
        _service(session_factory).create(
            actor=other_actor,
            command=_command(case_id),
            now=NOW,
        )


def test_creation_command_rejects_raw_file_and_invalid_source_hash():
    payload = _command(uuid4()).model_dump(mode="json")
    payload["payload"] = "raw-file-content"
    with pytest.raises(ValidationError):
        CreatePricingImportPreviewCommand.model_validate(payload)

    with pytest.raises(ValidationError):
        CreatePricingImportPreviewCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            case_id=uuid4(),
            document_kind="DPGF",
            source_sha256="not-a-hash",
            rows=[],
        )

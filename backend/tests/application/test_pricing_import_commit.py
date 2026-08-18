from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_pricing_import import build_patron_pricing_import_router
from app.modules.pricing.application.import_commands import CommitPricingImportCommand
from app.modules.pricing.application.import_preview import PricingImportPreviewService
from app.modules.pricing.application.import_service import (
    PricingImportService,
    pricing_import_handlers,
)
from app.platform.events.dispatcher import CommandDispatcher, CommandExecutionError
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.context import ActorKind
from app.platform.security.models import (
    FinancialReportLineRecord,
    FinancialReportSnapshotRecord,
    PricingImportBatchRecord,
    PricingImportRowRecord,
    PricingImportTransitionRecord,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.application.test_financial_report_draft_lines import _seed_draft

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def _batch_and_rows(actor, case_id):
    batch = PricingImportBatchRecord(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        case_id=case_id,
        document_kind="BPU",
        source_sha256="b" * 64,
        state="PREVIEWED",
        aggregate_revision=1,
        row_count=2,
        valid_row_count=2,
        error_count=0,
        total_minor=32500,
        actor_id=actor.actor_id,
        membership_id=actor.membership_id,
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=actor.correlation_id,
    )
    rows = [
        PricingImportRowRecord(
            id=uuid4(),
            tenant_id=actor.tenant_id,
            batch_id=batch.id,
            row_number=2,
            code="A-01",
            designation="Terrassement",
            unit="m2",
            quantity_decimal="10",
            unit_price_minor=1250,
            total_minor=12500,
            error_codes_json=[],
        ),
        PricingImportRowRecord(
            id=uuid4(),
            tenant_id=actor.tenant_id,
            batch_id=batch.id,
            row_number=3,
            code="A-02",
            designation="Fondations",
            unit="m3",
            quantity_decimal="2",
            unit_price_minor=10000,
            total_minor=20000,
            error_codes_json=[],
        ),
    ]
    return batch, rows


def _service(session_factory):
    return PricingImportService(
        session_factory=session_factory,
        dispatcher=CommandDispatcher(
            session_factory=session_factory,
            handlers=pricing_import_handlers(),
        ),
        policy=AuthorizationPolicy(),
    )


def _command(case_id, report_id, batch_id, *, command_id=None, expected_report_revision=0):
    return CommitPricingImportCommand(
        command_id=command_id or uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        case_id=case_id,
        report_id=report_id,
        batch_id=batch_id,
        expected_batch_revision=1,
        expected_report_revision=expected_report_revision,
    )


def test_patron_commits_import_atomically_and_replays_without_duplicates(session_factory):
    actor, case_id, report_id, _ = _seed_draft(session_factory)
    batch, rows = _batch_and_rows(actor, case_id)
    with session_factory.begin() as session:
        session.add(batch)
        session.add_all(rows)
    command = _command(case_id, report_id, batch.id)

    first = _service(session_factory).commit(actor=actor, command=command, now=NOW)
    replay = _service(session_factory).commit(actor=actor, command=command, now=NOW)

    assert first.result_code == "PRICING_IMPORT_COMMITTED"
    assert replay.replayed is True
    with session_factory() as session:
        snapshot = session.get(FinancialReportSnapshotRecord, report_id)
        lines = session.scalars(
            sa.select(FinancialReportLineRecord).where(
                FinancialReportLineRecord.snapshot_id == report_id
            )
        ).all()
        transitions = session.scalars(
            sa.select(PricingImportTransitionRecord).where(
                PricingImportTransitionRecord.batch_id == batch.id
            )
        ).all()
        events = session.scalars(
            sa.select(DomainEventRecord).where(DomainEventRecord.aggregate_id == report_id)
        ).all()
        outbox = session.scalars(
            sa.select(OutboxMessageRecord).where(
                OutboxMessageRecord.event_id.in_({event.id for event in events})
            )
        ).all()
    assert snapshot.sales_total_minor == 32500
    assert snapshot.aggregate_revision == 1
    assert len(lines) == 2
    assert len(transitions) == 1
    assert transitions[0].to_state == "COMMITTED"
    assert len(events) == 1
    assert len(outbox) == 1


def test_patron_commit_rejects_import_errors_and_revision_conflicts(session_factory):
    actor, case_id, report_id, _ = _seed_draft(session_factory)
    batch, rows = _batch_and_rows(actor, case_id)
    batch.error_count = 1
    batch.valid_row_count = 1
    with session_factory.begin() as session:
        session.add(batch)
        session.add_all(rows)
    with pytest.raises(CommandExecutionError, match="IMPORT_HAS_ERRORS"):
        _service(session_factory).commit(
            actor=actor,
            command=_command(case_id, report_id, batch.id),
            now=NOW,
        )

    conflict_batch, conflict_rows = _batch_and_rows(actor, case_id)
    with session_factory.begin() as session:
        session.add(conflict_batch)
        session.add_all(conflict_rows)
    conflict_command = _command(case_id, report_id, conflict_batch.id)
    conflict_command.expected_batch_revision = 2
    with pytest.raises(CommandExecutionError, match="VERSION_CONFLICT"):
        _service(session_factory).commit(actor=actor, command=conflict_command, now=NOW)


def test_commit_pricing_import_http_contract(session_factory):
    actor, case_id, report_id, _ = _seed_draft(session_factory)
    batch, rows = _batch_and_rows(actor, case_id)
    with session_factory.begin() as session:
        session.add(batch)
        session.add_all(rows)

    class _Resolver:
        def resolve(self, *, access_token):
            assert access_token == "test-token"
            return actor

    app = FastAPI()
    app.include_router(
        build_patron_pricing_import_router(
            service=PricingImportPreviewService(policy=AuthorizationPolicy()),
            commit_service=_service(session_factory),
            security_runtime=ConsultationSecurityRuntime(
                context_resolver=_Resolver(), policy=AuthorizationPolicy()
            ),
        )
    )
    payload = {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "report_id": str(report_id),
        "expected_batch_revision": 1,
        "expected_report_revision": 0,
    }
    client = TestClient(app)
    first = client.post(
        f"/api/v1/patron/cases/{case_id}/pricing-import/{batch.id}/commit",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )
    replay = client.post(
        f"/api/v1/patron/cases/{case_id}/pricing-import/{batch.id}/commit",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )
    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["replayed"] is True
    assert "total_minor" not in str(first.json())
    assert "designation" not in str(first.json())


def test_collaborator_cannot_commit_financial_import(session_factory):
    actor, case_id, report_id, _ = _seed_draft(session_factory)
    collaborator = replace(actor, actor_kind=ActorKind.COLLABORATEUR, membership_id=uuid4())
    batch, rows = _batch_and_rows(actor, case_id)
    with session_factory.begin() as session:
        session.add(batch)
        session.add_all(rows)
    with pytest.raises(PermissionError, match="FINANCIAL_REPORT_PATRON_REQUIRED"):
        _service(session_factory).commit(
            actor=collaborator,
            command=_command(case_id, report_id, batch.id),
            now=NOW,
        )

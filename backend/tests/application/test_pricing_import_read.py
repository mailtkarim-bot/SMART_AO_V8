from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.modules.pricing.application.import_read import PricingImportReadService
from app.platform.security.audit import AuditedAuthorizationPolicy, SecurityAuditWriter
from app.platform.security.authorization import AuthorizationDecision, AuthorizationPolicy
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorKind, DataClassification
from app.platform.security.models import (
    PricingImportTransitionRecord,
    SecurityAuditEventRecord,
)

from tests.application.test_financial_report_draft_lines import _seed_draft
from tests.application.test_pricing_import_commit import _batch_and_rows

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


class _DenyPolicy:
    def authorize(self, *, context, request):
        return AuthorizationDecision.denied(reason="test")


class _RecordingPolicy:
    def __init__(self):
        self.requests = []

    def authorize(self, *, context, request):
        self.requests.append(request)
        return AuthorizationDecision.allow()


def _service(session_factory, *, policy=None):
    return PricingImportReadService(
        session_factory=session_factory,
        policy=policy or AuthorizationPolicy(),
    )


def _persist_batch(session_factory, actor, case_id):
    batch, rows = _batch_and_rows(actor, case_id)
    with session_factory.begin() as session:
        session.add(batch)
        session.add_all(rows)
    return batch


def test_persisted_reader_denial_is_audited_without_business_payload(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    batch = _persist_batch(session_factory, actor, case_id)
    service = PricingImportReadService(
        session_factory=session_factory,
        policy=AuditedAuthorizationPolicy(
            policy=_DenyPolicy(),
            session_factory=session_factory,
            writer=SecurityAuditWriter(),
        ),
    )

    with pytest.raises(PermissionError, match="FORBIDDEN"):
        service.get(actor=actor, case_id=case_id, batch_id=batch.id, now=NOW)

    with session_factory() as session:
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord)
            .where(
                SecurityAuditEventRecord.tenant_id == actor.tenant_id,
                SecurityAuditEventRecord.action
                == "financial.report.line.write",
                SecurityAuditEventRecord.resource_id == batch.id,
            )
            .order_by(SecurityAuditEventRecord.occurred_at.desc())
            .limit(1)
        )

    assert audit is not None
    assert audit.event_type == "AUTHZ_DENIED"
    assert audit.metadata_json == {"channel": "policy"}
    assert "total_minor" not in audit.metadata_json


def test_persisted_reader_uses_financial_line_write_private_policy(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    batch = _persist_batch(session_factory, actor, case_id)
    policy = _RecordingPolicy()

    _service(session_factory, policy=policy).get(
        actor=actor,
        case_id=case_id,
        batch_id=batch.id,
        now=NOW,
    )

    request = policy.requests[0]
    assert request.action == Capability.FINANCIAL_REPORT_LINE_WRITE
    assert request.resource.classification is DataClassification.FINANCIAL_PRIVATE


def test_patron_reads_ordered_normalized_preview_rows(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    batch = _persist_batch(session_factory, actor, case_id)

    projection = _service(session_factory).get(
        actor=actor,
        case_id=case_id,
        batch_id=batch.id,
        now=NOW,
    )

    assert projection.batch_id == batch.id
    assert projection.case_id == case_id
    assert projection.document_kind == "BPU"
    assert projection.state == "PREVIEWED"
    assert projection.aggregate_revision == 1
    assert projection.row_count == 2
    assert projection.valid_row_count == 2
    assert projection.error_count == 0
    assert projection.total_minor == 32500
    assert [row.row_number for row in projection.rows] == [2, 3]
    assert projection.rows[0].designation == "Terrassement"
    assert projection.rows[1].total_minor == 20000


def test_patron_read_preserves_preview_validation_errors(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    batch, rows = _batch_and_rows(actor, case_id)
    batch.error_count = 1
    batch.valid_row_count = 1
    rows[1].designation = None
    rows[1].quantity_decimal = None
    rows[1].unit_price_minor = None
    rows[1].total_minor = None
    rows[1].error_codes_json = ["DESIGNATION_REQUIRED", "QUANTITY_REQUIRED"]
    with session_factory.begin() as session:
        session.add(batch)
        session.add_all(rows)

    projection = _service(session_factory).get(
        actor=actor,
        case_id=case_id,
        batch_id=batch.id,
        now=NOW,
    )

    assert projection.error_count == 1
    assert projection.rows[1].errors == ("DESIGNATION_REQUIRED", "QUANTITY_REQUIRED")
    assert projection.rows[1].designation is None


def test_collaborator_cannot_read_private_pricing_import(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    batch = _persist_batch(session_factory, actor, case_id)
    collaborator = replace(actor, actor_kind=ActorKind.COLLABORATEUR)

    with pytest.raises(PermissionError, match="FORBIDDEN"):
        _service(session_factory).get(
            actor=collaborator,
            case_id=case_id,
            batch_id=batch.id,
            now=NOW,
        )


def test_read_does_not_cross_tenant_boundaries(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    other_actor, other_case_id, _, _ = _seed_draft(session_factory)
    batch = _persist_batch(session_factory, actor, case_id)

    with pytest.raises(PermissionError, match="NOT_FOUND_OR_FORBIDDEN"):
        _service(session_factory).get(
            actor=other_actor,
            case_id=other_case_id,
            batch_id=batch.id,
            now=NOW,
        )


def test_read_reflects_latest_committed_transition(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    batch = _persist_batch(session_factory, actor, case_id)
    transition = PricingImportTransitionRecord(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        batch_id=batch.id,
        from_state="PREVIEWED",
        to_state="COMMITTED",
        version=2,
        actor_id=actor.actor_id,
        membership_id=actor.membership_id,
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=actor.correlation_id,
    )
    with session_factory.begin() as session:
        session.add(transition)

    projection = _service(session_factory).get(
        actor=actor,
        case_id=case_id,
        batch_id=batch.id,
        now=NOW,
    )

    assert projection.state == "COMMITTED"
    assert projection.aggregate_revision == 2


def test_read_hides_source_hash_and_non_projection_columns(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    batch = _persist_batch(session_factory, actor, case_id)
    projection = _service(session_factory).get(
        actor=actor,
        case_id=case_id,
        batch_id=batch.id,
        now=NOW,
    )

    assert not hasattr(projection, "source_sha256")
    assert not hasattr(projection, "filename")
    assert not hasattr(projection.rows[0], "payload")

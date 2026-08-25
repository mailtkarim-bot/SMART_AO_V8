import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.decision.domain.submission_gate import DecisionSubmissionGateSnapshot
from app.modules.submission.application.service import (
    PrepareSubmissionPackageHandler,
    SubmissionPackageService,
)
from app.modules.submission.infrastructure.decision_gate_reader import (
    SqlAlchemySubmissionDecisionGateReader,
)
from app.platform.events.dispatcher import CommandContext, CommandExecutionError
from app.platform.security.context import ActorKind
from sqlalchemy.dialects import postgresql

NOW_CASE_ID = uuid4()


def _context() -> CommandContext:
    return CommandContext(
        tenant_id=uuid4(),
        actor_id=uuid4(),
        actor_kind=ActorKind.PATRON_ADMIN.value,
        received_at=datetime.now(UTC),
        membership_id=uuid4(),
    )


def _command():
    return SimpleNamespace(
        preparation_package_id=uuid4(),
        expected_preparation_revision=2,
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
    )


def _session_for_gate_check() -> SimpleNamespace:
    preparation = SimpleNamespace(
        aggregate_revision=2,
        state="GENERATED",
        id=uuid4(),
        case_id=NOW_CASE_ID,
        dce_version_id=uuid4(),
        assignment_id=uuid4(),
    )
    readiness = SimpleNamespace(state="READY")
    document = SimpleNamespace(id=uuid4(), version=1, document_kind="TECHNICAL_RESPONSE")
    snapshot = SimpleNamespace(id=uuid4(), aggregate_revision=1)
    values = iter([preparation, readiness, document, snapshot])
    return SimpleNamespace(scalar=lambda *_args, **_kwargs: next(values))


class _Reader:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = []

    def read(self, **kwargs):
        self.calls.append(kwargs)
        return self.snapshot


@pytest.mark.application
@pytest.mark.security
def test_prepare_handler_blocks_before_enterprise_manifest_when_decision_is_not_ready() -> None:
    reader = _Reader(
        DecisionSubmissionGateSnapshot(
            lifecycle="FINALIZED",
            outcome="NO_GO",
            context_status="FROZEN",
            condition_status="NOT_APPLICABLE",
            open_condition_count=0,
            unresolved_risk_action_count=0,
            all_dce_requirements_confirmed=True,
        )
    )
    handler = PrepareSubmissionPackageHandler(decision_gate_reader=reader)

    with pytest.raises(CommandExecutionError, match="DECISION_SUBMISSION_BLOCKED"):
        handler.execute(
            session=_session_for_gate_check(),
            command=_command(),
            context=_context(),
        )

    assert len(reader.calls) == 1
    assert reader.calls[0]["case_id"] == NOW_CASE_ID


@pytest.mark.application
@pytest.mark.security
def test_prepare_handler_fails_closed_when_decision_gate_reader_is_not_configured() -> None:
    with pytest.raises(CommandExecutionError, match="DECISION_GATE_NOT_CONFIGURED"):
        PrepareSubmissionPackageHandler().execute(
            session=_session_for_gate_check(),
            command=_command(),
            context=_context(),
        )


@pytest.mark.application
@pytest.mark.security
def test_export_blocks_before_storage_read_when_decision_is_not_ready() -> None:
    tenant_id = uuid4()
    package_id = uuid4()
    manifest = {"schema_version": 2}
    manifest_bytes = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    record = SimpleNamespace(
        tenant_id=tenant_id,
        id=package_id,
        case_id=NOW_CASE_ID,
        manifest_json=manifest,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        technical_document_id=uuid4(),
    )
    document = SimpleNamespace(storage_key="private/technical-response.md")
    session = MagicMock()
    session.scalar.side_effect = [record, document]
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    session_factory.begin.return_value.__enter__.return_value = MagicMock()
    storage = MagicMock()
    reader = _Reader(
        DecisionSubmissionGateSnapshot(
            lifecycle="FINALIZED",
            outcome="NO_GO",
            context_status="FROZEN",
            condition_status="NOT_APPLICABLE",
            open_condition_count=0,
            unresolved_risk_action_count=0,
            all_dce_requirements_confirmed=True,
        )
    )
    actor = SimpleNamespace(
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_id=uuid4(),
        tenant_id=tenant_id,
        actor_id=uuid4(),
        identity_id=uuid4(),
        session_id=uuid4(),
        correlation_id=uuid4(),
    )
    policy = SimpleNamespace(authorize=lambda **_kwargs: SimpleNamespace(allowed=True))
    service = SubmissionPackageService(
        session_factory=session_factory,
        dispatcher=MagicMock(),
        policy=policy,
        storage=storage,
        decision_gate_reader=reader,
    )

    with pytest.raises(CommandExecutionError, match="DECISION_SUBMISSION_BLOCKED"):
        service.export(actor=actor, submission_package_id=package_id, now=datetime.now(UTC))

    storage.read.assert_not_called()


class _ReaderSession:
    def __init__(self, *, decision, applicable_version, condition_count, action_rows):
        self._scalar_values = iter([decision, applicable_version, condition_count])
        self._action_rows = action_rows
        self.statements = []

    def scalar(self, statement):
        self.statements.append(statement)
        return next(self._scalar_values)

    def scalars(self, statement):
        self.statements.append(statement)
        return []

    def execute(self, statement):
        self.statements.append(statement)
        return SimpleNamespace(all=lambda: self._action_rows)


@pytest.mark.application
@pytest.mark.security
def test_sqlalchemy_reader_compiles_postgresql_and_selects_no_financial_columns() -> None:
    decision = SimpleNamespace(
        id=uuid4(),
        selected_final_context_id=uuid4(),
        lifecycle="FINALIZED",
        outcome="GO",
        context_status="FROZEN",
        condition_status="NOT_APPLICABLE",
        cycle_number=1,
        updated_at=None,
    )
    session = _ReaderSession(
        decision=decision,
        applicable_version=uuid4(),
        condition_count=0,
        action_rows=[],
    )

    snapshot = SqlAlchemySubmissionDecisionGateReader().read(
        session=session,
        tenant_id=uuid4(),
        case_id=NOW_CASE_ID,
    )

    assert snapshot is not None
    assert snapshot.outcome == "GO"
    compiled = "\n".join(
        str(statement.compile(dialect=postgresql.dialect())) for statement in session.statements
    )
    assert "tenant_id" in compiled
    assert "case_id" in compiled
    assert "COMPLETED" in compiled or "decision" in compiled
    for forbidden in (
        "quantity_decimal",
        "unit_price_minor",
        "total_minor",
        "sales_total_minor",
        "gross_margin_minor",
    ):
        assert forbidden not in compiled

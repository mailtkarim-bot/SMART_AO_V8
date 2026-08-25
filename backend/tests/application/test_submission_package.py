from __future__ import annotations

import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.decision.domain.submission_gate import DecisionSubmissionGateSnapshot
from app.modules.preparation.application.commands import GenerateTechnicalDocumentCommand
from app.modules.preparation.application.service import PreparationService, preparation_handlers
from app.modules.preparation.infrastructure.dce_preparation_reader import (
    SqlAlchemyPreparationDceReader,
)
from app.modules.preparation.infrastructure.document_storage import LocalGeneratedDocumentStorage
from app.modules.submission.application.commands import PrepareSubmissionPackageCommand
from app.modules.submission.application.ports import SubmissionDecisionGateReader
from app.modules.submission.application.service import (
    PrepareSubmissionPackageHandler,
    SubmissionPackageService,
    submission_handlers,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
)
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import capabilities_for
from app.platform.security.context import ActorKind
from app.platform.security.models import (
    FinancialReportSnapshotRecord,
    SecurityAuditEventRecord,
    SubmissionPackageRecord,
)
from sqlalchemy.orm import Session, sessionmaker

from tests.application.test_collab_work_task import NOW, _seed
from tests.application.test_preparation_completeness import (
    _confirm_requirement,
    _dce_version_id,
    _enable_preparation_scope,
    _readiness_command,
    _seed_capability_assessment,
)

pytest_plugins = ("tests.application.test_collab_work_task",)


class _ReadySubmissionDecisionGateReader:
    def read(self, *, session, tenant_id, case_id):
        return DecisionSubmissionGateSnapshot(
            lifecycle="FINALIZED",
            outcome="GO",
            context_status="FROZEN",
            condition_status="NOT_APPLICABLE",
            open_condition_count=0,
            unresolved_risk_action_count=0,
            all_dce_requirements_confirmed=True,
        )


@pytest.fixture
def services(session_factory: sessionmaker[Session], tmp_path):
    storage = LocalGeneratedDocumentStorage(root=tmp_path / "generated")
    decision_gate_reader: SubmissionDecisionGateReader = _ReadySubmissionDecisionGateReader()
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={
            **preparation_handlers(
                storage=storage,
                dce_reader=SqlAlchemyPreparationDceReader(),
            ),
            **submission_handlers(decision_gate_reader=decision_gate_reader),
        },
    )
    policy = AuthorizationPolicy()
    preparation = PreparationService(
        session_factory=session_factory,
        dispatcher=dispatcher,
        policy=policy,
        storage=storage,
    )
    submission = SubmissionPackageService(
        session_factory=session_factory,
        dispatcher=dispatcher,
        policy=policy,
        storage=storage,
        decision_gate_reader=decision_gate_reader,
    )
    return preparation, submission


def _prepare_generated_document(services, session_factory):
    preparation, _ = services
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    actor = _enable_preparation_scope(session_factory, actor, assignment_id)
    dce_version_id = _dce_version_id(session_factory, actor.tenant_id)
    package_id = uuid4()
    preparation.execute(
        actor=actor,
        command=_readiness_command(
            actor=actor,
            assignment_id=assignment_id,
            case_id=case_id,
            dce_version_id=dce_version_id,
            package_id=package_id,
            expected_revision=0,
        ),
        now=NOW,
    )
    _confirm_requirement(session_factory, actor=actor, requirement_id=requirement_id)
    preparation.execute(
        actor=actor,
        command=_readiness_command(
            actor=actor,
            assignment_id=assignment_id,
            case_id=case_id,
            dce_version_id=dce_version_id,
            package_id=package_id,
            expected_revision=1,
        ),
        now=NOW,
    )
    document_id = uuid4()
    preparation.execute(
        actor=actor,
        command=GenerateTechnicalDocumentCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            package_id=package_id,
            document_id=document_id,
            expected_revision=2,
            readiness_revision=2,
            document_kind="TECHNICAL_RESPONSE",
        ),
        now=NOW,
    )
    patron = replace(
        actor,
        actor_kind=ActorKind.PATRON_ADMIN,
        capabilities=capabilities_for(ActorKind.PATRON_ADMIN),
    )
    return patron, package_id, case_id


def _publish_snapshot(session_factory, *, tenant_id, case_id) -> UUID:
    snapshot_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            FinancialReportSnapshotRecord(
                id=snapshot_id,
                tenant_id=tenant_id,
                case_id=case_id,
                state="PUBLISHED",
                currency_code="EUR",
                ruleset_version=1,
                aggregate_revision=4,
                calculated_at=NOW,
                published_at=NOW,
                sales_total_minor=100_000,
                direct_cost_total_minor=40_000,
                overhead_total_minor=10_000,
                subcontracting_total_minor=0,
                contingency_total_minor=5_000,
                gross_margin_minor=45_000,
                gross_margin_rate_bps=4500,
                forecast_cashflow_minor=45_000,
            )
        )
    return snapshot_id


@pytest.mark.db
@pytest.mark.security
def test_submission_package_is_hashed_idempotent_and_append_only(services, session_factory) -> None:
    _, submission = services
    actor, preparation_package_id, case_id = _prepare_generated_document(services, session_factory)
    snapshot_id = _publish_snapshot(session_factory, tenant_id=actor.tenant_id, case_id=case_id)
    command = PrepareSubmissionPackageCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        preparation_package_id=preparation_package_id,
        expected_preparation_revision=3,
    )

    prepared = submission.prepare(actor=actor, command=command, now=NOW)
    replay = submission.prepare(actor=actor, command=command, now=NOW)

    assert prepared.result_code == "SUBMISSION_PACKAGE_PREPARED"
    assert replay.replayed is True
    package_id = prepared.aggregate_refs[0]["aggregate_id"]
    archive = submission.export(actor=actor, submission_package_id=UUID(package_id), now=NOW)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        names = sorted(bundle.namelist())
        exported_manifest = json.loads(bundle.read("manifest.json"))
        technical_content = bundle.read("technical-response.md")
    assert names == ["manifest.json", "technical-response.md"]
    assert exported_manifest["schema_version"] == 2
    assert "storage_key" not in str(exported_manifest)
    assert "sales_total_minor" not in str(exported_manifest)
    assert technical_content.startswith("# Réponse technique".encode())
    with session_factory() as session:
        record = session.get(SubmissionPackageRecord, package_id)
        assert record is not None
        assert record.state == "PRET_CONTROLE"
        assert record.financial_snapshot_id == snapshot_id
        assert record.manifest_json["external_submission"] == "NOT_PERFORMED"
        assert "sales_total_minor" not in str(record.manifest_json)
        assert session.scalar(
            sa.select(sa.func.count()).where(
                SubmissionPackageRecord.tenant_id == actor.tenant_id,
                SubmissionPackageRecord.preparation_package_id == preparation_package_id,
            )
        ) == 1
        assert session.scalar(
            sa.select(sa.func.count()).where(
                DomainEventRecord.tenant_id == actor.tenant_id,
                DomainEventRecord.aggregate_id == record.id,
            )
        ) == 2
        assert session.scalar(
            sa.select(sa.func.count()).where(OutboxMessageRecord.tenant_id == actor.tenant_id)
        ) >= 2
        audit = session.scalar(
            sa.select(SecurityAuditEventRecord).where(
                SecurityAuditEventRecord.tenant_id == actor.tenant_id,
                SecurityAuditEventRecord.action == "submission.export",
            )
        )
        notification = session.scalar(
            sa.select(OutboxMessageRecord).where(
                OutboxMessageRecord.tenant_id == actor.tenant_id,
                OutboxMessageRecord.topic == "submission.package.exported",
            )
        )
        assert audit is not None
        assert audit.event_type == "SUBMISSION_PACKAGE_EXPORTED"
        assert audit.metadata_json == {"channel": "download"}
        assert notification is not None
        assert notification.payload_json["archive_sha256"]
        smtp_notification = session.scalar(
            sa.select(OutboxMessageRecord).where(
                OutboxMessageRecord.tenant_id == actor.tenant_id,
                OutboxMessageRecord.topic == "submission.package.exported.smtp",
            )
        )
        assert smtp_notification is not None
        assert smtp_notification.event_id == notification.event_id
        assert smtp_notification.payload_json == {
            "submission_package_id": str(record.id),
            "delivery": "EXPORT_READY",
        }
        assert "archive_sha256" not in smtp_notification.payload_json
        assert "financial_snapshot_id" not in smtp_notification.payload_json


    with pytest.raises(sa.exc.ProgrammingError), session_factory.begin() as session:
        session.execute(
            sa.update(SubmissionPackageRecord)
            .where(SubmissionPackageRecord.tenant_id == actor.tenant_id)
            .values(state="AUTORISE_DEPOT")
        )


@pytest.mark.db
@pytest.mark.security
def test_submission_export_rejects_missing_unauthorized_unconfigured_and_corrupt_inputs(
    services, session_factory
) -> None:
    _, submission = services
    actor, preparation_package_id, case_id = _prepare_generated_document(services, session_factory)
    _publish_snapshot(session_factory, tenant_id=actor.tenant_id, case_id=case_id)
    with pytest.raises(PermissionError, match="NOT_FOUND_OR_FORBIDDEN"):
        submission.export(actor=actor, submission_package_id=uuid4(), now=NOW)

    collaborator = replace(actor, actor_kind=ActorKind.COLLABORATEUR)
    with pytest.raises(PermissionError, match="SUBMISSION_PATRON_REQUIRED"):
        submission.export(actor=collaborator, submission_package_id=uuid4(), now=NOW)

    unconfigured = SubmissionPackageService(
        session_factory=session_factory,
        dispatcher=submission._dispatcher,  # noqa: SLF001
        policy=AuthorizationPolicy(),
    )
    with pytest.raises(RuntimeError, match="SUBMISSION_EXPORT_STORAGE_NOT_CONFIGURED"):
        unconfigured.export(actor=actor, submission_package_id=uuid4(), now=NOW)

    prepared = submission.prepare(
        actor=actor,
        command=PrepareSubmissionPackageCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            preparation_package_id=preparation_package_id,
            expected_preparation_revision=3,
        ),
        now=NOW,
    )
    package_id = prepared.aggregate_refs[0]["aggregate_id"]
    with pytest.raises(sa.exc.ProgrammingError), session_factory.begin() as session:
        session.execute(
            sa.update(SubmissionPackageRecord)
            .where(SubmissionPackageRecord.id == package_id)
            .values(manifest_json={"schema_version": 999})
        )


@pytest.mark.concurrency
@pytest.mark.db
@pytest.mark.security
def test_concurrent_submission_manifest_assembly_serializes_versions_without_duplicates(
    services, session_factory
) -> None:
    _, submission = services
    actor, preparation_package_id, case_id = _prepare_generated_document(services, session_factory)
    _publish_snapshot(session_factory, tenant_id=actor.tenant_id, case_id=case_id)
    commands = [
        PrepareSubmissionPackageCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            preparation_package_id=preparation_package_id,
            expected_preparation_revision=3,
        )
        for _ in range(6)
    ]

    def assemble(command: PrepareSubmissionPackageCommand):
        return submission.prepare(actor=actor, command=command, now=NOW)

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(assemble, commands))

    assert all(result.result_code == "SUBMISSION_PACKAGE_PREPARED" for result in results)
    with session_factory() as session:
        records = list(
            session.scalars(
                sa.select(SubmissionPackageRecord)
                .where(
                    SubmissionPackageRecord.tenant_id == actor.tenant_id,
                    SubmissionPackageRecord.preparation_package_id == preparation_package_id,
                )
                .order_by(SubmissionPackageRecord.version)
            )
        )
    assert [record.version for record in records] == list(range(1, 7))
    assert len({record.manifest_sha256 for record in records}) == 1
    assert all(record.manifest_json["schema_version"] == 2 for record in records)


@pytest.mark.db
@pytest.mark.security
def test_submission_manifest_freezes_validated_enterprise_capability_proofs(
    services, session_factory
) -> None:
    preparation, submission = services
    actor, assignment_id, case_id, _, _ = _seed_capability_assessment(
        session_factory,
        proof_status="VALIDATED",
        proof_expires_at=NOW.replace(year=2027),
    )
    dce_version_id = _dce_version_id(session_factory, actor.tenant_id)
    preparation_package_id = uuid4()
    preparation.execute(
        actor=actor,
        command=_readiness_command(
            actor=actor,
            assignment_id=assignment_id,
            case_id=case_id,
            dce_version_id=dce_version_id,
            package_id=preparation_package_id,
            expected_revision=0,
        ),
        now=NOW,
    )
    preparation.execute(
        actor=actor,
        command=GenerateTechnicalDocumentCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            package_id=preparation_package_id,
            document_id=uuid4(),
            expected_revision=1,
            readiness_revision=1,
            document_kind="TECHNICAL_RESPONSE",
        ),
        now=NOW,
    )
    patron = replace(
        actor,
        actor_kind=ActorKind.PATRON_ADMIN,
        capabilities=capabilities_for(ActorKind.PATRON_ADMIN),
    )
    snapshot_id = _publish_snapshot(session_factory, tenant_id=actor.tenant_id, case_id=case_id)
    result = submission.prepare(
        actor=patron,
        command=PrepareSubmissionPackageCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            preparation_package_id=preparation_package_id,
            expected_preparation_revision=2,
        ),
        now=NOW,
    )
    with session_factory() as session:
        record = session.get(SubmissionPackageRecord, result.aggregate_refs[0]["aggregate_id"])
    assert record is not None
    assert record.financial_snapshot_id == snapshot_id
    enterprise_entries = [
        entry
        for entry in record.manifest_json["entries"]
        if entry["kind"] == "ENTERPRISE_CAPABILITY"
    ]
    assert len(enterprise_entries) == 1
    assert enterprise_entries[0]["proof_documents"][0]["document_kind"] == "INSURANCE"
    assert "storage_key" not in str(record.manifest_json)
    assert "sales_total_minor" not in str(record.manifest_json)


@pytest.mark.db
@pytest.mark.security
def test_submission_package_requires_published_snapshot_and_current_revision(
    services, session_factory
) -> None:
    _, submission = services
    actor, preparation_package_id, case_id = _prepare_generated_document(services, session_factory)
    command = PrepareSubmissionPackageCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        preparation_package_id=preparation_package_id,
        expected_preparation_revision=3,
    )
    with pytest.raises(CommandExecutionError, match="OFFICIAL_PRICE_NOT_PUBLISHED"):
        submission.prepare(actor=actor, command=command, now=NOW)

    _publish_snapshot(session_factory, tenant_id=actor.tenant_id, case_id=case_id)
    with pytest.raises(CommandExecutionError, match="VERSION_CONFLICT"):
        submission.prepare(
            actor=actor,
            command=command.model_copy(update={"expected_preparation_revision": 2}),
            now=NOW,
        )


class _ScalarSequence:
    def __init__(self, values: list[object]) -> None:
        self._values = iter(values)

    def next(self) -> object:
        return next(self._values)


class _EnterpriseBranchSession:
    def __init__(self, *, scalar_values: list[object], scalars_values: list[list[object]]) -> None:
        self._scalar_values = _ScalarSequence(scalar_values)
        self._scalars_values = _ScalarSequence(
            [SimpleNamespace(all=lambda values=values: values) for values in scalars_values]
        )

    def scalar(self, *_args, **_kwargs) -> object:
        return self._scalar_values.next()

    def scalars(self, *_args, **_kwargs) -> object:
        return self._scalars_values.next()


def _enterprise_branch_inputs() -> tuple[SimpleNamespace, CommandContext, SimpleNamespace]:
    proposal = SimpleNamespace(
        validity_state="CURRENT",
        capability_id=uuid4(),
        capability_version_id=uuid4(),
    )
    preparation = SimpleNamespace(case_id=uuid4(), assignment_id=uuid4())
    context = CommandContext(
        tenant_id=uuid4(),
        actor_id=uuid4(),
        actor_kind=ActorKind.PATRON_ADMIN.value,
        received_at=NOW,
        membership_id=uuid4(),
    )
    return proposal, context, preparation


def _active_capability_version(
    proposal: SimpleNamespace,
) -> tuple[SimpleNamespace, SimpleNamespace]:
    capability = SimpleNamespace(
        id=proposal.capability_id,
        company_id=uuid4(),
        state="ACTIVE",
        capability_kind="PLUMBER",
        name="Qualification",
        summary="Qualification BTP",
    )
    version = SimpleNamespace(
        id=proposal.capability_version_id,
        capability_id=proposal.capability_id,
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=30),
        version_number=1,
        title="Version 1",
        description="Description",
        usage_scope="France",
    )
    return capability, version


def test_submission_manifest_rejects_expired_capability_proposal() -> None:
    proposal, context, preparation = _enterprise_branch_inputs()
    proposal.validity_state = "EXPIRED"
    session = _EnterpriseBranchSession(scalar_values=[], scalars_values=[[proposal]])

    with pytest.raises(CommandExecutionError, match="CAPABILITY_PROOF_EXPIRED"):
        PrepareSubmissionPackageHandler()._validated_enterprise_entries(  # noqa: SLF001
            session=session, preparation=preparation, context=context
        )


@pytest.mark.parametrize("capability_state", ["INACTIVE", "MISSING"])
def test_submission_manifest_rejects_unauthorized_capability(capability_state: str) -> None:
    proposal, context, preparation = _enterprise_branch_inputs()
    capability, version = _active_capability_version(proposal)
    capability = (
        None
        if capability_state == "MISSING"
        else SimpleNamespace(
            **{**vars(capability), "state": "INACTIVE"}
        )
    )
    session = _EnterpriseBranchSession(
        scalar_values=[capability, version], scalars_values=[[proposal]]
    )

    with pytest.raises(CommandExecutionError, match="CAPABILITY_PROOF_UNAUTHORIZED"):
        PrepareSubmissionPackageHandler()._validated_enterprise_entries(  # noqa: SLF001
            session=session, preparation=preparation, context=context
        )


def test_submission_manifest_rejects_version_outside_validity_window() -> None:
    proposal, context, preparation = _enterprise_branch_inputs()
    capability, version = _active_capability_version(proposal)
    version.valid_from = NOW + timedelta(days=1)
    session = _EnterpriseBranchSession(
        scalar_values=[capability, version], scalars_values=[[proposal]]
    )

    with pytest.raises(CommandExecutionError, match="CAPABILITY_PROOF_EXPIRED"):
        PrepareSubmissionPackageHandler()._validated_enterprise_entries(  # noqa: SLF001
            session=session, preparation=preparation, context=context
        )


def test_submission_manifest_rejects_missing_proof_link() -> None:
    proposal, context, preparation = _enterprise_branch_inputs()
    capability, version = _active_capability_version(proposal)
    session = _EnterpriseBranchSession(
        scalar_values=[capability, version], scalars_values=[[proposal], []]
    )

    with pytest.raises(CommandExecutionError, match="CAPABILITY_PROOF_MISSING"):
        PrepareSubmissionPackageHandler()._validated_enterprise_entries(  # noqa: SLF001
            session=session, preparation=preparation, context=context
        )


@pytest.mark.parametrize(
    ("company_matches", "verification_status", "expired"),
    [(False, "VALIDATED", False), (True, "PENDING", False), (True, "VALIDATED", True)],
)
def test_submission_manifest_rejects_invalid_proof_document(
    company_matches: bool, verification_status: str, expired: bool
) -> None:
    proposal, context, preparation = _enterprise_branch_inputs()
    capability, version = _active_capability_version(proposal)
    link = SimpleNamespace(document_id=uuid4())
    document = SimpleNamespace(
        id=link.document_id,
        company_id=capability.company_id if company_matches else uuid4(),
        verification_status=verification_status,
        expires_at=NOW - timedelta(days=1) if expired else NOW + timedelta(days=1),
    )
    session = _EnterpriseBranchSession(
        scalar_values=[capability, version, document], scalars_values=[[proposal], [link]]
    )
    expected = "CAPABILITY_PROOF_EXPIRED" if expired else "CAPABILITY_PROOF_UNAUTHORIZED"

    with pytest.raises(CommandExecutionError, match=expected):
        PrepareSubmissionPackageHandler()._validated_enterprise_entries(  # noqa: SLF001
            session=session, preparation=preparation, context=context
        )


class _AllowPolicy:
    def __init__(self, allowed: bool, code: str = "DENIED") -> None:
        self._allowed = allowed
        self._code = code

    def authorize(self, **_kwargs):
        return SimpleNamespace(allowed=self._allowed, code=self._code)


def _patron_actor() -> SimpleNamespace:
    return SimpleNamespace(
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_id=uuid4(),
        tenant_id=uuid4(),
        actor_id=uuid4(),
        identity_id=uuid4(),
        session_id=uuid4(),
        correlation_id=uuid4(),
    )


def _service_with_session(values: list[object], *, policy: object) -> SubmissionPackageService:
    from unittest.mock import MagicMock

    session = MagicMock()
    session.scalar.side_effect = values
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session
    storage = SimpleNamespace(read=lambda **_kwargs: b"technical")
    return SubmissionPackageService(
        session_factory=factory,
        dispatcher=MagicMock(),
        policy=policy,
        storage=storage,
    )


def test_submission_export_rejects_unauthorized_policy() -> None:
    actor = _patron_actor()
    service = _service_with_session([], policy=_AllowPolicy(False, "DENIED"))

    with pytest.raises(PermissionError, match="DENIED"):
        service.export(actor=actor, submission_package_id=uuid4(), now=NOW)


def test_submission_export_rejects_corrupt_manifest() -> None:
    import hashlib

    actor = _patron_actor()
    manifest = {"schema_version": 2}
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    record = SimpleNamespace(
        tenant_id=actor.tenant_id,
        id=uuid4(),
        manifest_json=manifest,
        manifest_sha256=hashlib.sha256(b"wrong").hexdigest(),
    )
    service = _service_with_session([record], policy=_AllowPolicy(True))

    with pytest.raises(CommandExecutionError, match="SUBMISSION_MANIFEST_INTEGRITY_FAILED"):
        service.export(actor=actor, submission_package_id=record.id, now=NOW)

    assert manifest_bytes != b"wrong"


def test_submission_export_requires_technical_document() -> None:
    import hashlib

    actor = _patron_actor()
    manifest = {"schema_version": 2}
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    record = SimpleNamespace(
        tenant_id=actor.tenant_id,
        id=uuid4(),
        manifest_json=manifest,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        technical_document_id=uuid4(),
    )
    service = _service_with_session([record, None], policy=_AllowPolicy(True))

    with pytest.raises(CommandExecutionError, match="TECHNICAL_DOCUMENT_REQUIRED"):
        service.export(actor=actor, submission_package_id=record.id, now=NOW)


def test_submission_prepare_rejects_actor_and_policy() -> None:
    service = SubmissionPackageService(
        session_factory=SimpleNamespace(),
        dispatcher=SimpleNamespace(dispatch=lambda **_kwargs: None),
        policy=_AllowPolicy(True),
    )
    collaborator = _patron_actor()
    collaborator.actor_kind = ActorKind.COLLABORATEUR
    command = PrepareSubmissionPackageCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        preparation_package_id=uuid4(),
        expected_preparation_revision=1,
    )
    with pytest.raises(PermissionError, match="SUBMISSION_PATRON_REQUIRED"):
        service.prepare(actor=collaborator, command=command, now=NOW)

    with pytest.raises(PermissionError, match="DENIED"):
        SubmissionPackageService(
            session_factory=SimpleNamespace(),
            dispatcher=SimpleNamespace(dispatch=lambda **_kwargs: None),
            policy=_AllowPolicy(False, "DENIED"),
        ).prepare(actor=_patron_actor(), command=command, now=NOW)


def _handler_context(actor_kind: str = ActorKind.PATRON_ADMIN.value) -> CommandContext:
    return CommandContext(
        tenant_id=uuid4(),
        actor_id=uuid4(),
        actor_kind=actor_kind,
        received_at=NOW,
        membership_id=uuid4(),
    )


def _handler_session(values: list[object]) -> SimpleNamespace:
    iterator = iter(values)
    return SimpleNamespace(scalar=lambda *_args, **_kwargs: next(iterator))


@pytest.mark.parametrize(
    ("preparation", "error"),
    [
        (None, "NOT_FOUND_OR_FORBIDDEN"),
        (SimpleNamespace(aggregate_revision=1, state="DRAFT"), "VERSION_CONFLICT"),
        (SimpleNamespace(aggregate_revision=2, state="DRAFT"), "PREPARATION_NOT_GENERATED"),
    ],
)
def test_prepare_handler_rejects_invalid_preparation_states(
    preparation: object, error: str
) -> None:
    command = SimpleNamespace(
        preparation_package_id=uuid4(),
        expected_preparation_revision=2,
    )
    if error == "VERSION_CONFLICT":
        preparation.aggregate_revision = 1
    with pytest.raises(CommandExecutionError, match=error):
        PrepareSubmissionPackageHandler().execute(
            session=_handler_session([preparation]),
            command=command,
            context=_handler_context(),
        )


@pytest.mark.parametrize("readiness", [None, SimpleNamespace(state="BLOCKED")])
def test_prepare_handler_rejects_missing_or_blocked_readiness(readiness: object) -> None:
    preparation = SimpleNamespace(
        aggregate_revision=2,
        state="GENERATED",
        id=uuid4(),
        case_id=uuid4(),
    )
    command = SimpleNamespace(
        preparation_package_id=uuid4(),
        expected_preparation_revision=2,
    )
    error = "READINESS_NOT_FOUND" if readiness is None else "PREPARATION_BLOCKED"
    with pytest.raises(CommandExecutionError, match=error):
        PrepareSubmissionPackageHandler().execute(
            session=_handler_session([preparation, readiness]),
            command=command,
            context=_handler_context(),
        )


def test_prepare_handler_requires_generated_technical_document() -> None:
    preparation = SimpleNamespace(
        aggregate_revision=2,
        state="GENERATED",
        id=uuid4(),
        case_id=uuid4(),
    )
    readiness = SimpleNamespace(state="READY")
    command = SimpleNamespace(
        preparation_package_id=uuid4(),
        expected_preparation_revision=2,
    )
    with pytest.raises(CommandExecutionError, match="TECHNICAL_DOCUMENT_REQUIRED"):
        PrepareSubmissionPackageHandler().execute(
            session=_handler_session([preparation, readiness, None]),
            command=command,
            context=_handler_context(),
        )


def test_prepare_handler_rejects_non_patron_context() -> None:
    command = SimpleNamespace(
        preparation_package_id=uuid4(),
        expected_preparation_revision=1,
    )
    with pytest.raises(CommandExecutionError, match="SUBMISSION_PATRON_REQUIRED"):
        PrepareSubmissionPackageHandler().execute(
            session=_handler_session([]),
            command=command,
            context=_handler_context(actor_kind=ActorKind.COLLABORATEUR.value),
        )

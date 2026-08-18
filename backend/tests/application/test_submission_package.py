from __future__ import annotations

from dataclasses import replace
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.preparation.application.commands import GenerateTechnicalDocumentCommand
from app.modules.preparation.application.service import PreparationService, preparation_handlers
from app.modules.preparation.infrastructure.dce_preparation_reader import (
    SqlAlchemyPreparationDceReader,
)
from app.modules.preparation.infrastructure.document_storage import LocalGeneratedDocumentStorage
from app.modules.submission.application.commands import PrepareSubmissionPackageCommand
from app.modules.submission.application.service import SubmissionPackageService, submission_handlers
from app.platform.events.dispatcher import CommandDispatcher, CommandExecutionError
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import capabilities_for
from app.platform.security.context import ActorKind
from app.platform.security.models import (
    FinancialReportSnapshotRecord,
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


@pytest.fixture
def services(session_factory: sessionmaker[Session], tmp_path):
    storage = LocalGeneratedDocumentStorage(root=tmp_path / "generated")
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={
            **preparation_handlers(
                storage=storage,
                dce_reader=SqlAlchemyPreparationDceReader(),
            ),
            **submission_handlers(),
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
        ) == 1
        assert session.scalar(
            sa.select(sa.func.count()).where(OutboxMessageRecord.tenant_id == actor.tenant_id)
        ) >= 1

    with pytest.raises(sa.exc.ProgrammingError), session_factory.begin() as session:
        session.execute(
            sa.update(SubmissionPackageRecord)
            .where(SubmissionPackageRecord.tenant_id == actor.tenant_id)
            .values(state="AUTORISE_DEPOT")
        )


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

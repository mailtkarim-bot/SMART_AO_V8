from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.preparation.application.service import PreparationService, preparation_handlers
from app.modules.preparation.infrastructure.dce_preparation_reader import (
    SqlAlchemyPreparationDceReader,
)
from app.modules.preparation.infrastructure.document_storage import LocalGeneratedDocumentStorage
from app.modules.submission.application.commands import PrepareSubmissionPackageCommand
from app.modules.submission.application.evidence_commands import RecordSubmissionEvidenceCommand
from app.modules.submission.application.evidence_service import (
    SubmissionEvidenceService,
    submission_evidence_handlers,
)
from app.modules.submission.application.service import SubmissionPackageService, submission_handlers
from app.platform.events.dispatcher import CommandDispatcher
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.models import SubmissionEvidenceRecord
from sqlalchemy.orm import Session, sessionmaker

from tests.application.test_submission_package import (
    _prepare_generated_document,
    _publish_snapshot,
)

pytest_plugins = ("tests.application.test_submission_package",)


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
    return (
        PreparationService(
            session_factory=session_factory,
            dispatcher=dispatcher,
            policy=policy,
            storage=storage,
        ),
        SubmissionPackageService(
            session_factory=session_factory,
            dispatcher=dispatcher,
            policy=policy,
        ),
    )


NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


@pytest.mark.db
@pytest.mark.security
def test_manual_submission_evidence_is_hashed_idempotent_and_append_only(
    services, session_factory
) -> None:
    _, submission = services
    actor, preparation_package_id, case_id = _prepare_generated_document(services, session_factory)
    _publish_snapshot(session_factory, tenant_id=actor.tenant_id, case_id=case_id)
    package_result = submission.prepare(
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
    package_id = UUID(package_result.aggregate_refs[0]["aggregate_id"])
    evidence = SubmissionEvidenceService(
        dispatcher=CommandDispatcher(
            session_factory=session_factory,
            handlers=submission_evidence_handlers(),
        ),
        policy=AuthorizationPolicy(),
    )
    command = RecordSubmissionEvidenceCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        evidence_id=uuid4(),
        submission_package_id=package_id,
        evidence_type="MANUAL_RECEIPT",
        external_reference_hash="a" * 64,
        evidence_sha256="b" * 64,
        notes_redacted="Saisi manuellement par le patron.",
    )
    created = evidence.execute(actor=replace(actor), command=command, now=NOW)
    replay = evidence.execute(actor=actor, command=command, now=NOW)
    assert created.result_code == "SUBMISSION_EVIDENCE_RECORDED"
    assert replay.replayed is True
    with session_factory() as session:
        record = session.get(SubmissionEvidenceRecord, command.evidence_id)
        assert record is not None
        assert record.status == "RECEIVED"
        assert record.evidence_sha256 == "b" * 64
        assert "external_submission" not in record.notes_redacted
        with pytest.raises(sa.exc.DatabaseError), session.begin_nested():
            session.execute(
                sa.update(SubmissionEvidenceRecord)
                .where(SubmissionEvidenceRecord.id == command.evidence_id)
                .values(status="REJECTED")
            )

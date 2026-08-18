from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.modules.submission.application.signature_service import (
    SubmissionSignatureHandler,
    submission_signature_handlers,
)
from app.platform.events.dispatcher import CommandContext, CommandExecutionError

TENANT_ID = uuid4()
ACTOR_ID = uuid4()
MEMBERSHIP_ID = uuid4()


def _context() -> CommandContext:
    return CommandContext(
        tenant_id=TENANT_ID,
        actor_id=ACTOR_ID,
        actor_kind="PATRON",
        received_at=datetime.now(tz=UTC),
        membership_id=MEMBERSHIP_ID,
    )


def _request_command() -> SimpleNamespace:
    return SimpleNamespace(
        command_type="RequestSubmissionSignature",
        signature_id=uuid4(),
        submission_package_id=uuid4(),
        expected_package_version=2,
        provider="DOCUSIGN",
        signer_membership_id=uuid4(),
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
    )


def _callback_command() -> SimpleNamespace:
    return SimpleNamespace(
        command_type="RecordSubmissionSignature",
        signature_id=uuid4(),
        provider="DOCUSIGN",
        outcome="SIGNED",
        provider_reference_hash="a" * 64,
        signature_sha256="b" * 64,
    )


def _session(result: object) -> SimpleNamespace:
    return SimpleNamespace(scalar=lambda *_args, **_kwargs: result, add=lambda _record: None)


def test_request_signature_creates_append_only_intent() -> None:
    command = _request_command()
    package = SimpleNamespace(
        id=command.submission_package_id,
        tenant_id=TENANT_ID,
        case_id=uuid4(),
        version=2,
    )
    added: list[object] = []
    session = SimpleNamespace(
        scalar=lambda *_args, **_kwargs: package,
        add=added.append,
    )

    outcome = SubmissionSignatureHandler().execute(
        session=session, command=command, context=_context()
    )

    assert outcome.result_code == "SUBMISSION_SIGNATURE_REQUESTED"
    assert len(added) == 1
    assert added[0].status == "REQUESTED"
    assert outcome.events[0].payload["provider"] == "DOCUSIGN"


def test_request_signature_rejects_missing_package() -> None:
    command = _request_command()
    with pytest.raises(CommandExecutionError, match="NOT_FOUND_OR_FORBIDDEN"):
        SubmissionSignatureHandler().execute(
            session=_session(None), command=command, context=_context()
        )


def test_request_signature_rejects_version_conflict() -> None:
    command = _request_command()
    package = SimpleNamespace(version=1)
    with pytest.raises(CommandExecutionError, match="VERSION_CONFLICT"):
        SubmissionSignatureHandler().execute(
            session=_session(package), command=command, context=_context()
        )


def test_callback_records_signed_fact() -> None:
    command = _callback_command()
    record = SimpleNamespace(
        id=command.signature_id,
        provider="DOCUSIGN",
        status="REQUESTED",
        submission_package_id=uuid4(),
    )

    outcome = SubmissionSignatureHandler().execute(
        session=_session(record), command=command, context=_context()
    )

    assert outcome.result_code == "SUBMISSION_SIGNATURE_RECORDED"
    assert record.status == "SIGNED"
    assert record.provider_reference_hash == "a" * 64
    assert record.signature_sha256 == "b" * 64


def test_callback_rejects_missing_or_wrong_provider() -> None:
    command = _callback_command()
    with pytest.raises(CommandExecutionError, match="NOT_FOUND_OR_FORBIDDEN"):
        SubmissionSignatureHandler().execute(
            session=_session(None), command=command, context=_context()
        )
    record = SimpleNamespace(provider="OTHER", status="REQUESTED")
    with pytest.raises(CommandExecutionError, match="NOT_FOUND_OR_FORBIDDEN"):
        SubmissionSignatureHandler().execute(
            session=_session(record), command=command, context=_context()
        )


def test_callback_rejects_finalized_signature() -> None:
    command = _callback_command()
    record = SimpleNamespace(provider="DOCUSIGN", status="SIGNED")
    with pytest.raises(CommandExecutionError, match="SIGNATURE_ALREADY_FINALIZED"):
        SubmissionSignatureHandler().execute(
            session=_session(record), command=command, context=_context()
        )


def test_handler_rejects_unsupported_command_and_exposes_bindings() -> None:
    command = SimpleNamespace(command_type="UnknownSignatureCommand")
    with pytest.raises(CommandExecutionError, match="UNSUPPORTED_SIGNATURE_COMMAND"):
        SubmissionSignatureHandler().execute(
            session=_session(None), command=command, context=_context()
        )
    handlers = submission_signature_handlers()
    assert set(handlers) == {"RequestSubmissionSignature", "RecordSubmissionSignature"}

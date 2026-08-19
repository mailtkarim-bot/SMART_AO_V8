from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.modules.enterprise.application.enterprise_upload import (
    FinalizeEnterpriseDocumentUploadHandler,
    PrepareEnterpriseDocumentUploadHandler,
    VerifyEnterpriseDocumentHandler,
)
from app.platform.events.dispatcher import CommandContext, CommandExecutionError
from app.platform.security.context import ActorKind

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


class SessionDouble:
    def __init__(self, values: list[object]) -> None:
        self._values = iter(values)
        self.added: list[object] = []

    def scalar(self, *_args, **_kwargs) -> object:
        return next(self._values)

    def add(self, value: object) -> None:
        self.added.append(value)


def _context(actor_kind: str = ActorKind.PATRON_ADMIN.value) -> CommandContext:
    return CommandContext(
        tenant_id=uuid4(),
        actor_id=uuid4(),
        actor_kind=actor_kind,
        received_at=NOW,
        membership_id=uuid4(),
    )


def _prepare_command() -> SimpleNamespace:
    return SimpleNamespace(
        upload_id=uuid4(),
        company_id=uuid4(),
        document_id=uuid4(),
        document_kind="KBIS",
        document_label="Kbis",
        original_filename="kbis.pdf",
        storage_key="private/kbis",
        expected_byte_size=12,
        expires_at=NOW + timedelta(days=1),
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
    )


def _finalize_command() -> SimpleNamespace:
    return SimpleNamespace(
        upload_id=uuid4(),
        company_id=uuid4(),
        document_id=uuid4(),
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
    )


def _verify_command() -> SimpleNamespace:
    return SimpleNamespace(
        company_id=uuid4(),
        document_id=uuid4(),
        expected_verification_revision=0,
        outcome="VALIDATED",
        reason_code="DOCUMENT_ACCEPTED",
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
    )


def test_prepare_handler_rejects_non_patron_and_missing_company() -> None:
    command = _prepare_command()
    with pytest.raises(CommandExecutionError, match="ENTERPRISE_LIBRARY_PATRON_REQUIRED"):
        PrepareEnterpriseDocumentUploadHandler().execute(
            session=SessionDouble([]), command=command, context=_context("COLLABORATEUR")
        )
    with pytest.raises(CommandExecutionError, match="NOT_FOUND_OR_FORBIDDEN"):
        PrepareEnterpriseDocumentUploadHandler().execute(
            session=SessionDouble([None]), command=command, context=_context()
        )


def test_prepare_handler_rejects_duplicate_and_creates_upload() -> None:
    command = _prepare_command()
    company = SimpleNamespace(id=command.company_id)
    with pytest.raises(CommandExecutionError, match="ENTERPRISE_UPLOAD_ALREADY_EXISTS"):
        PrepareEnterpriseDocumentUploadHandler().execute(
            session=SessionDouble([company, SimpleNamespace()]), command=command, context=_context()
        )
    session = SessionDouble([company, None])
    outcome = PrepareEnterpriseDocumentUploadHandler().execute(
        session=session, command=command, context=_context()
    )
    assert outcome.result_code == "ENTERPRISE_DOCUMENT_UPLOAD_PREPARED"
    assert len(session.added) == 1
    assert session.added[0].state == "AWAITING_UPLOAD"


def test_finalize_handler_rejects_guards_and_registers_clean_document() -> None:
    command = _finalize_command()
    handler = FinalizeEnterpriseDocumentUploadHandler()
    with pytest.raises(CommandExecutionError, match="ENTERPRISE_LIBRARY_PATRON_REQUIRED"):
        handler.execute(
            session=SessionDouble([]), command=command, context=_context("COLLABORATEUR")
        )
    with pytest.raises(CommandExecutionError, match="NOT_FOUND_OR_FORBIDDEN"):
        handler.execute(session=SessionDouble([None]), command=command, context=_context())
    not_clean = SimpleNamespace(state="QUARANTINED", sha256="a" * 64)
    with pytest.raises(CommandExecutionError, match="DOCUMENT_UPLOAD_NOT_CLEAN"):
        handler.execute(session=SessionDouble([not_clean]), command=command, context=_context())
    clean = SimpleNamespace(
        state="CLEAN",
        sha256="a" * 64,
        document_kind="KBIS",
        document_label="Kbis",
        original_filename="kbis.pdf",
        expires_at=NOW + timedelta(days=1),
    )
    with pytest.raises(CommandExecutionError, match="NOT_FOUND_OR_FORBIDDEN"):
        handler.execute(session=SessionDouble([clean, None]), command=command, context=_context())
    company = SimpleNamespace(id=command.company_id, aggregate_revision=4)
    with pytest.raises(CommandExecutionError, match="ENTERPRISE_DOCUMENT_ALREADY_EXISTS"):
        handler.execute(
            session=SessionDouble([clean, company, SimpleNamespace()]),
            command=command,
            context=_context(),
        )
    session = SessionDouble([clean, company, None])
    outcome = handler.execute(session=session, command=command, context=_context())
    assert outcome.result_code == "ENTERPRISE_DOCUMENT_REGISTERED"
    assert company.aggregate_revision == 5
    assert session.added[0].verification_status == "PENDING"


def test_verify_handler_rejects_guards_and_revision_then_records_verification() -> None:
    command = _verify_command()
    handler = VerifyEnterpriseDocumentHandler()
    with pytest.raises(CommandExecutionError, match="ENTERPRISE_LIBRARY_PATRON_REQUIRED"):
        handler.execute(
            session=SessionDouble([]), command=command, context=_context("COLLABORATEUR")
        )
    document = SimpleNamespace(id=command.document_id)
    with pytest.raises(CommandExecutionError, match="NOT_FOUND_OR_FORBIDDEN"):
        handler.execute(session=SessionDouble([None]), command=command, context=_context())
    with pytest.raises(CommandExecutionError, match="DOCUMENT_UPLOAD_NOT_CLEAN"):
        handler.execute(
            session=SessionDouble([document, None]), command=command, context=_context()
        )
    clean_upload = SimpleNamespace(state="CLEAN")
    current = SimpleNamespace(revision=2)
    with pytest.raises(CommandExecutionError, match="VERSION_CONFLICT"):
        handler.execute(
            session=SessionDouble([document, clean_upload, current]),
            command=command,
            context=_context(),
        )
    session = SessionDouble([document, clean_upload, None])
    outcome = handler.execute(session=session, command=command, context=_context())
    assert outcome.result_code == "ENTERPRISE_DOCUMENT_VERIFIED"
    assert session.added[0].revision == 0
    assert outcome.events[0].payload["outcome"] == "VALIDATED"

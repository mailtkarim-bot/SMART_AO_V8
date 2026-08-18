from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.modules.enterprise.application.enterprise_upload_commands import (
    PrepareEnterpriseDocumentUploadCommand,
    VerifyEnterpriseDocumentCommand,
)
from pydantic import ValidationError

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def _prepare_payload() -> dict[str, object]:
    return {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
        "upload_id": uuid4(),
        "company_id": uuid4(),
        "document_id": uuid4(),
        "document_kind": "KBIS",
        "document_label": "Extrait Kbis",
        "original_filename": "kbis.pdf",
        "expected_byte_size": 1024,
        "storage_key": f"{uuid4()}/{uuid4()}/{uuid4()}.bin",
        "expires_at": NOW + timedelta(hours=1),
    }


def test_prepare_upload_accepts_only_positive_size_and_closed_document_kind() -> None:
    command = PrepareEnterpriseDocumentUploadCommand(**_prepare_payload())

    assert command.document_kind == "KBIS"
    assert command.expected_byte_size == 1024

    with pytest.raises(ValidationError):
        PrepareEnterpriseDocumentUploadCommand(**{**_prepare_payload(), "document_kind": "SECRET"})
    with pytest.raises(ValidationError):
        PrepareEnterpriseDocumentUploadCommand(**{**_prepare_payload(), "expected_byte_size": 0})


def test_prepare_upload_rejects_client_controlled_storage_path() -> None:
    with pytest.raises(ValidationError):
        PrepareEnterpriseDocumentUploadCommand(
            **{**_prepare_payload(), "storage_key": "../escape.bin"}
        )


def test_verify_command_has_closed_human_outcomes_and_reason() -> None:
    command = VerifyEnterpriseDocumentCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        company_id=uuid4(),
        document_id=uuid4(),
        expected_verification_revision=0,
        outcome="VALIDATED",
        reason_code="DOCUMENT_ACCEPTED",
    )

    assert command.outcome == "VALIDATED"
    with pytest.raises(ValidationError):
        VerifyEnterpriseDocumentCommand(**{**command.model_dump(), "outcome": "APPROVED"})

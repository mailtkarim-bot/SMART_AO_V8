from uuid import uuid4

import pytest
from app.modules.submission.application.signature_commands import (
    RecordSubmissionSignatureCommand,
    RequestSubmissionSignatureCommand,
)
from pydantic import ValidationError


def test_signature_request_contract_is_closed_and_provider_normalized() -> None:
    command = RequestSubmissionSignatureCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        signature_id=uuid4(),
        submission_package_id=uuid4(),
        expected_package_version=1,
        signer_membership_id=uuid4(),
        provider="DOCUSIGN",
    )
    assert command.provider == "DOCUSIGN"
    assert command.expected_package_version == 1


def test_signature_callback_requires_hashes_and_closed_outcome() -> None:
    command = RecordSubmissionSignatureCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        signature_id=uuid4(),
        submission_package_id=uuid4(),
        provider="DOCUSIGN",
        provider_reference_hash="a" * 64,
        signature_sha256="b" * 64,
        outcome="SIGNED",
    )
    assert command.outcome == "SIGNED"


@pytest.mark.parametrize(
    "field,value",
    [("provider_reference_hash", "not-a-hash"), ("signature_sha256", "not-a-hash")],
)
def test_signature_callback_rejects_unhashed_provider_facts(field: str, value: str) -> None:
    payload = {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
        "signature_id": uuid4(),
        "submission_package_id": uuid4(),
        "provider": "DOCUSIGN",
        "provider_reference_hash": "a" * 64,
        "signature_sha256": "b" * 64,
        "outcome": "SIGNED",
    }
    payload[field] = value
    with pytest.raises(ValidationError):
        RecordSubmissionSignatureCommand(**payload)

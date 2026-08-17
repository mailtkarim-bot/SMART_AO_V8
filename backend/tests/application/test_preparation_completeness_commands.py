from uuid import uuid4

import pytest
from app.modules.preparation.application.commands import (
    EvaluatePreparationReadinessCommand,
    GenerateTechnicalDocumentCommand,
)
from pydantic import ValidationError


def _envelope() -> dict[str, object]:
    return {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
    }


def test_readiness_command_is_closed_and_server_scoped() -> None:
    command = EvaluatePreparationReadinessCommand(
        **_envelope(),
        package_id=uuid4(),
        case_id=uuid4(),
        assignment_id=uuid4(),
        dce_version_id=uuid4(),
        expected_revision=0,
    )

    assert command.command_type == "EvaluatePreparationReadiness"
    with pytest.raises(ValidationError):
        EvaluatePreparationReadinessCommand(
            **_envelope(),
            package_id=uuid4(),
            case_id=uuid4(),
            assignment_id=uuid4(),
            dce_version_id=uuid4(),
            expected_revision=0,
            tenant_id=uuid4(),
        )


def test_generate_command_does_not_accept_client_document_content() -> None:
    command = GenerateTechnicalDocumentCommand(
        **_envelope(),
        package_id=uuid4(),
        document_id=uuid4(),
        expected_revision=1,
        readiness_revision=1,
        document_kind="TECHNICAL_RESPONSE",
    )

    assert command.command_type == "GenerateTechnicalDocument"
    with pytest.raises(ValidationError):
        GenerateTechnicalDocumentCommand(
            **_envelope(),
            package_id=uuid4(),
            document_id=uuid4(),
            expected_revision=1,
            readiness_revision=1,
            document_kind="TECHNICAL_RESPONSE",
            content="prix et marge",
        )

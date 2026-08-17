from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.modules.membership.application.collab_info_blockers_commands import (
    CreateInformationRequestCommand,
    DeclareTaskBlockerCommand,
    RecordInformationRequestResponseCommand,
    ResolveTaskBlockerCommand,
)
from pydantic import ValidationError

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def _envelope() -> dict[str, object]:
    return {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
    }


def test_create_information_request_is_closed_and_operational() -> None:
    command = CreateInformationRequestCommand(
        **_envelope(),
        request_id=uuid4(),
        task_id=uuid4(),
        expected_task_revision=1,
        request_kind="MISSING_SOURCE",
        subject="Source de l’exigence",
        question="Pouvez-vous confirmer la page de référence du RC ?",
        requested_object="Localisation de la source",
        reason="La source est nécessaire pour vérifier l’exigence.",
        priority="HIGH",
        due_at=NOW,
    )

    assert command.command_type == "CreateInformationRequest"
    with pytest.raises(ValidationError):
        CreateInformationRequestCommand(
            **_envelope(),
            request_id=uuid4(),
            task_id=uuid4(),
            expected_task_revision=1,
            request_kind="MISSING_SOURCE",
            subject="Source",
            question="Question",
            requested_object="Objet",
            reason="Motif",
            priority="NORMAL",
            financial_amount=100,
        )


def test_information_contract_rejects_finance_and_closed_values() -> None:
    with pytest.raises(ValidationError, match="FINANCIAL_DATA_FORBIDDEN"):
        CreateInformationRequestCommand(
            **_envelope(),
            request_id=uuid4(),
            task_id=uuid4(),
            expected_task_revision=1,
            request_kind="MISSING_SOURCE",
            subject="Prix demandé",
            question="Quel est le prix et la marge ?",
            requested_object="Donnée",
            reason="Besoin de contrôle",
            priority="NORMAL",
        )
    with pytest.raises(ValidationError):
        CreateInformationRequestCommand(
            **_envelope(),
            request_id=uuid4(),
            task_id=uuid4(),
            expected_task_revision=1,
            request_kind="UNKNOWN",
            subject="Sujet",
            question="Question",
            requested_object="Objet",
            reason="Motif",
            priority="NORMAL",
        )


def test_response_and_blocker_commands_are_versioned_and_closed() -> None:
    response = RecordInformationRequestResponseCommand(
        **_envelope(),
        request_id=uuid4(),
        expected_revision=1,
        response_text="La source est RC:p8.",
        source_locator="RC:p8",
        outcome="ANSWERED",
    )
    blocker = DeclareTaskBlockerCommand(
        **_envelope(),
        task_id=uuid4(),
        expected_revision=2,
        blocker_id=uuid4(),
        blocker_kind="MISSING_INFORMATION",
        description="La source doit être confirmée avant clôture.",
        source_locator="RC:p8",
        resolution_owner="PATRON_ADMIN",
    )
    resolved = ResolveTaskBlockerCommand(
        **_envelope(),
        task_id=blocker.task_id,
        blocker_id=blocker.blocker_id,
        expected_revision=3,
        resolution_note="Réponse reçue et contrôlée.",
    )

    assert response.command_type == "RecordInformationRequestResponse"
    assert blocker.command_type == "DeclareTaskBlocker"
    assert resolved.command_type == "ResolveTaskBlocker"
    with pytest.raises(ValidationError, match="FINANCIAL_DATA_FORBIDDEN"):
        RecordInformationRequestResponseCommand(
            **_envelope(),
            request_id=uuid4(),
            expected_revision=1,
            response_text="La marge prévue est 12%.",
            outcome="ANSWERED",
        )

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.modules.membership.application.collab_work_task_commands import (
    ClaimTaskCommand,
    CompleteTaskCommand,
    CreateTaskFromRequirementCommand,
    RecordTaskResultCommand,
)
from pydantic import ValidationError

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def _base() -> dict[str, object]:
    return {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
    }


def test_create_task_command_is_closed_and_requires_operational_content() -> None:
    command = CreateTaskFromRequirementCommand(
        **_base(),
        task_id=uuid4(),
        assignment_id=uuid4(),
        case_id=uuid4(),
        requirement_id=uuid4(),
        task_kind="REQUIREMENT_CHECK",
        title="Vérifier les modalités de visite",
        objective="Confirmer la source et signaler toute incertitude.",
        due_at=NOW + timedelta(days=2),
    )
    assert command.task_kind == "REQUIREMENT_CHECK"
    assert "price" not in command.model_dump()

    with pytest.raises(ValidationError):
        CreateTaskFromRequirementCommand(
            **_base(),
            task_id=uuid4(),
            assignment_id=uuid4(),
            case_id=uuid4(),
            requirement_id=uuid4(),
            task_kind="REQUIREMENT_CHECK",
            title="Tâche",
            objective="Objectif",
            price=100,
        )


def test_result_command_requires_bounded_non_financial_evidence_or_reason() -> None:
    command = RecordTaskResultCommand(
        **_base(),
        task_id=uuid4(),
        expected_revision=0,
        result_text="La visite est obligatoire selon le RC, page 8.",
        source_locator="RC:p8",
        outcome="RECORDED",
    )
    assert command.outcome == "RECORDED"

    with pytest.raises(ValidationError):
        RecordTaskResultCommand(
            **_base(),
            task_id=uuid4(),
            expected_revision=0,
            result_text="",
            source_locator=None,
            outcome="RECORDED",
        )

    with pytest.raises(ValidationError):
        RecordTaskResultCommand(
            **_base(),
            task_id=uuid4(),
            expected_revision=0,
            result_text="Coût estimé 1000 EUR",
            source_locator="RC:p8",
            outcome="RECORDED",
        )


def test_claim_and_complete_require_expected_revision() -> None:
    claim = ClaimTaskCommand(**_base(), task_id=uuid4(), expected_revision=0)
    complete = CompleteTaskCommand(**_base(), task_id=uuid4(), expected_revision=1)
    assert claim.expected_revision == 0
    assert complete.expected_revision == 1

    with pytest.raises(ValidationError):
        ClaimTaskCommand(**_base(), task_id=uuid4(), expected_revision=-1)

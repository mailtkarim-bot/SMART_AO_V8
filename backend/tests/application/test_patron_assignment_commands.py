from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.modules.dce.application.commands import (
    AmendCaseAssignmentScopeCommand,
    CreateCaseAssignmentCommand,
)
from pydantic import ValidationError

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)


def _create_payload() -> dict[str, object]:
    return {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
        "assignment_id": uuid4(),
        "case_id": uuid4(),
        "target_membership_id": uuid4(),
        "expected_case_revision": 3,
        "scope_actions": ["assignment.history.read", "case.dce.read"],
        "scope_classifications": ["INTERNAL_OPERATIONAL"],
        "starts_at": NOW,
        "ends_at": NOW + timedelta(days=7),
    }


def test_create_case_assignment_command_is_closed_and_canonicalizes_scope() -> None:
    command = CreateCaseAssignmentCommand(**_create_payload())

    assert command.scope_actions == ["assignment.history.read", "case.dce.read"]
    assert command.scope_classifications == ["INTERNAL_OPERATIONAL"]
    assert command.command_type == "CreateCaseAssignment"

    with pytest.raises(ValidationError):
        CreateCaseAssignmentCommand(**_create_payload(), tenant_id=uuid4())


@pytest.mark.parametrize(
    "field,value",
    [
        ("scope_actions", []),
        ("scope_actions", ["case.dce.read", "case.dce.read"]),
        ("scope_actions", ["pricing.read"]),
        ("scope_classifications", ["FINANCIAL_PRIVATE"]),
    ],
)
def test_create_case_assignment_command_rejects_closed_scope_violations(
    field: str,
    value: object,
) -> None:
    payload = _create_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        CreateCaseAssignmentCommand(**payload)


def test_create_case_assignment_command_rejects_invalid_period() -> None:
    payload = _create_payload()
    payload["ends_at"] = NOW

    with pytest.raises(ValidationError, match="strictly ordered"):
        CreateCaseAssignmentCommand(**payload)


def test_amend_case_assignment_scope_command_validates_closed_canonical_scope() -> None:
    command = AmendCaseAssignmentScopeCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        assignment_id=uuid4(),
        expected_revision=0,
        scope_actions=["preparation.transmit", "case.dce.read"],
        scope_classifications=["INTERNAL_OPERATIONAL"],
    )

    assert command.scope_actions == ["case.dce.read", "preparation.transmit"]

    with pytest.raises(ValidationError):
        AmendCaseAssignmentScopeCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            assignment_id=uuid4(),
            expected_revision=-1,
            scope_actions=["case.dce.read"],
            scope_classifications=["INTERNAL_OPERATIONAL"],
        )

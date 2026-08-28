from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from app.modules.membership.infrastructure.assignment_management_reader import (
    SqlAlchemyAssignmentManagementReader,
)
from app.platform.security.capabilities import Capability

from tests.support.actors import make_actor_context

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "command_type",
    (
        "CreateCaseAssignment",
        "AmendCaseAssignmentScope",
        "SuspendCaseAssignment",
        "ReactivateCaseAssignment",
        "EndCaseAssignment",
        "ValidateAssignmentInteraction",
    ),
)
def test_record_denial_supports_patron_assignment_commands(command_type: str) -> None:
    audit_writer = Mock()
    session_factory = MagicMock()
    reader = SqlAlchemyAssignmentManagementReader(session_factory, audit_writer=audit_writer)
    command = SimpleNamespace(
        command_type=command_type,
        assignment_id=uuid4(),
        command_id=uuid4(),
        correlation_id=uuid4(),
    )
    actor = make_actor_context()

    reader.record_denial(actor=actor, command=command, now=NOW, reason="DENIED")

    audit_writer.record.assert_called_once()
    entry = audit_writer.record.call_args.kwargs["entry"]
    assert entry.action == Capability.ASSIGNMENT_MANAGE.value
    assert entry.reason_code == "DENIED"

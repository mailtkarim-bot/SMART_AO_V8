from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from app.modules.membership.application.mutation_service import MembershipMutationService


@pytest.mark.parametrize(
    ("method_name", "delegate_name"),
    [
        ("create", "create"),
        ("amend_scope", "amend_scope"),
        ("suspend", "suspend"),
        ("reactivate", "reactivate"),
        ("end", "end"),
        ("validate_interaction", "validate_interaction"),
    ],
)
def test_patron_mutations_delegate_through_single_membership_boundary(
    method_name: str, delegate_name: str
) -> None:
    patron = Mock()
    collaborator = Mock()
    expected = object()
    getattr(patron, delegate_name).return_value = expected
    service = MembershipMutationService(
        patron_assignments=patron,
        collaborator_assignments=collaborator,
    )
    actor = object()
    command = object()
    now = datetime.now(tz=UTC)

    result = getattr(service, method_name)(actor=actor, command=command, now=now)

    assert result is expected
    getattr(patron, delegate_name).assert_called_once_with(actor=actor, command=command, now=now)


@pytest.mark.parametrize("method_name", ["acknowledge", "clarify", "report_unavailability"])
def test_collaborator_mutations_delegate_through_single_membership_boundary(
    method_name: str,
) -> None:
    patron = Mock()
    collaborator = Mock()
    expected = object()
    getattr(collaborator, method_name).return_value = expected
    service = MembershipMutationService(
        patron_assignments=patron,
        collaborator_assignments=collaborator,
    )
    actor = object()
    command = object()
    now = datetime.now(tz=UTC)

    result = getattr(service, method_name)(actor=actor, command=command, now=now)

    assert result is expected
    getattr(collaborator, method_name).assert_called_once_with(
        actor=actor, command=command, now=now
    )

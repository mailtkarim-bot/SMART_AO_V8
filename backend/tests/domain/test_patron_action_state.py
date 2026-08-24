from __future__ import annotations

import pytest
from app.modules.patron_action.domain.state import ensure_transition_allowed


@pytest.mark.domain
@pytest.mark.parametrize(
    ("current_state", "target_state"),
    (
        ("OPEN", "IN_PROGRESS"),
        ("OPEN", "WAITING"),
        ("OPEN", "ABANDONED"),
        ("IN_PROGRESS", "WAITING"),
        ("IN_PROGRESS", "COMPLETED"),
        ("IN_PROGRESS", "ABANDONED"),
        ("WAITING", "IN_PROGRESS"),
        ("WAITING", "ABANDONED"),
    ),
)
def test_allowed_patron_action_transition(
    current_state: str, target_state: str
) -> None:
    ensure_transition_allowed(current_state, target_state)


@pytest.mark.domain
@pytest.mark.parametrize(
    ("current_state", "target_state"),
    (
        ("OPEN", "COMPLETED"),
        ("COMPLETED", "OPEN"),
        ("ABANDONED", "IN_PROGRESS"),
        ("WAITING", "COMPLETED"),
        ("UNKNOWN", "OPEN"),
    ),
)
def test_forbidden_patron_action_transition(
    current_state: str, target_state: str
) -> None:
    with pytest.raises(ValueError):
        ensure_transition_allowed(current_state, target_state)

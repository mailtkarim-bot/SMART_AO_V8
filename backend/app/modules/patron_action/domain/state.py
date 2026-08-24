"""Pure state-machine rules for patron actions."""

from __future__ import annotations

from enum import StrEnum


class PatronActionState(StrEnum):
    """Persisted lifecycle states of a patron action."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


ALLOWED_TRANSITIONS: dict[PatronActionState, frozenset[PatronActionState]] = {
    PatronActionState.OPEN: frozenset(
        {
            PatronActionState.IN_PROGRESS,
            PatronActionState.WAITING,
            PatronActionState.ABANDONED,
        }
    ),
    PatronActionState.IN_PROGRESS: frozenset(
        {
            PatronActionState.WAITING,
            PatronActionState.COMPLETED,
            PatronActionState.ABANDONED,
        }
    ),
    PatronActionState.WAITING: frozenset(
        {
            PatronActionState.IN_PROGRESS,
            PatronActionState.ABANDONED,
        }
    ),
    PatronActionState.COMPLETED: frozenset(),
    PatronActionState.ABANDONED: frozenset(),
}


def ensure_transition_allowed(current_state: str, target_state: str) -> None:
    """Reject transitions not represented by the patron-action lifecycle."""

    try:
        current = PatronActionState(current_state)
        target = PatronActionState(target_state)
    except ValueError as exc:
        raise ValueError("unknown patron action state") from exc
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"transition {current.value}->{target.value} is not allowed")

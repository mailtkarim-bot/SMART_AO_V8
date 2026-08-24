from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.platform.events.dispatcher import CommandContext


@dataclass(frozen=True, slots=True)
class PatronActionReference:
    """Minimal cross-context reference returned by the patron-action port."""

    id: UUID
    case_id: UUID | None
    action_type: str
    severity: str
    state: str
    aggregate_revision: int


class PatronActionWriter(Protocol):
    """Public port used by another context to raise a factual patron action."""

    def create_from_preparation_transmission(
        self,
        *,
        session: Session,
        context: CommandContext,
        case_id: UUID,
        package_id: UUID,
        transmission_id: UUID,
        command_id: UUID,
        idempotency_key: UUID,
    ) -> PatronActionReference | None: ...


__all__ = ["PatronActionReference", "PatronActionWriter"]

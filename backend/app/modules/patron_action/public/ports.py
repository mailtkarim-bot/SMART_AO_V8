from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.platform.events.dispatcher import CommandContext
from app.platform.security.models import PatronActionRecord


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
    ) -> PatronActionRecord | None: ...

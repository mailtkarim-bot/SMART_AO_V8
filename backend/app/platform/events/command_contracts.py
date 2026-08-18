"""Framework-neutral command contract shared by bounded contexts."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApplicationCommand(BaseModel):
    """Closed Pydantic base for a server-resolved application intent."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    command_type: ClassVar[str]
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None

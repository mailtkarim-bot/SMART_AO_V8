"""Application ports for preparation read models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class PreparationRequirementInput:
    """Minimal DCE requirement facts used by deterministic readiness and generation."""

    requirement_id: UUID
    requirement_type: str
    directive_signal: str
    confirmation_outcome: str | None


@dataclass(frozen=True, slots=True)
class PreparationDceInput:
    """Minimal DCE projection exposed to preparation application logic."""

    analysis_readiness: str
    requirements: tuple[PreparationRequirementInput, ...]


class PreparationDceReader(Protocol):
    """Read-only DCE projection port owned by the preparation application."""

    def read(
        self,
        *,
        session: Session,
        tenant_id: UUID,
        dce_version_id: UUID,
        as_of: datetime,
    ) -> PreparationDceInput | None: ...

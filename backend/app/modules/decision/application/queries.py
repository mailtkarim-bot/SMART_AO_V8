from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DecisionDossierDecision:
    id: UUID
    case_id: UUID
    decision_type: str
    lifecycle: str
    outcome: str
    validity: str
    context_status: str
    final_justification: str | None


@dataclass(frozen=True, slots=True)
class DecisionDossierContext:
    id: UUID
    canonical_context_json: Mapping[str, object]
    unknowns_json: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class DecisionDossierReference:
    aggregate_type: str
    aggregate_id: UUID
    aggregate_revision: int
    reference_role: str


@dataclass(frozen=True, slots=True)
class DecisionDossierCondition:
    id: UUID
    label: str
    status: str
    due_at: datetime | None
    failure_consequence: str


@dataclass(frozen=True, slots=True)
class DecisionDossierLookup:
    decision: DecisionDossierDecision | None
    context: DecisionDossierContext | None
    references: tuple[DecisionDossierReference, ...]
    conditions: tuple[DecisionDossierCondition, ...]


class DecisionDossierReader(Protocol):
    """Reads one tenant-scoped patron dossier without exposing ORM records."""

    def read(self, *, tenant_id: UUID, case_id: UUID) -> DecisionDossierLookup: ...

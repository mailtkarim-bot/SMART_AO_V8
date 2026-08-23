"""Application service for creating version one of a watch profile."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.modules.opportunity.domain.watch_profile import (
    WatchProfileCriteria,
    WatchProfileState,
    normalize_profile_name,
)


@dataclass(frozen=True, slots=True)
class CreateWatchProfileCommand:
    profile_id: UUID
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None
    tenant_id: UUID
    actor_id: UUID
    name: str
    criteria: WatchProfileCriteria


@dataclass(frozen=True, slots=True)
class WatchProfileRecordInput:
    profile_id: UUID
    tenant_id: UUID
    actor_id: UUID
    name: str
    state: WatchProfileState
    version: int
    criteria_snapshot: dict[str, object]
    criteria_sha256: str
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None


@dataclass(frozen=True, slots=True)
class WatchProfilePersistenceResult:
    profile_id: UUID
    version: int
    state: WatchProfileState
    replayed: bool


class WatchProfileRepositoryPort(Protocol):
    def create_or_replay(
        self, record: WatchProfileRecordInput
    ) -> WatchProfilePersistenceResult: ...


class WatchProfileService:
    """Create a patron-owned profile without contacting any notice provider."""

    def __init__(self, *, repository: WatchProfileRepositoryPort) -> None:
        self._repository = repository

    def execute(self, command: CreateWatchProfileCommand) -> WatchProfilePersistenceResult:
        name = normalize_profile_name(command.name)
        criteria_snapshot = command.criteria.snapshot()
        criteria_sha256 = hashlib.sha256(_canonical_json(criteria_snapshot)).hexdigest()
        return self._repository.create_or_replay(
            WatchProfileRecordInput(
                profile_id=command.profile_id,
                tenant_id=command.tenant_id,
                actor_id=command.actor_id,
                name=name,
                state=WatchProfileState.ACTIVE,
                version=1,
                criteria_snapshot=criteria_snapshot,
                criteria_sha256=criteria_sha256,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )


def _canonical_json(value: dict[str, object]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )

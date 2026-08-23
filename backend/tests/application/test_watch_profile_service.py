from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID

from app.modules.opportunity.application.watch_profile_service import (
    CreateWatchProfileCommand,
    WatchProfileRecordInput,
    WatchProfileService,
)
from app.modules.opportunity.domain.watch_profile import ProjectType, WatchProfileCriteria

TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbb0001")
ACTOR_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbb0002")
PROFILE_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbb0003")
COMMAND_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbb0004")
IDEMPOTENCY_KEY = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbb0005")


@dataclass
class CapturingRepository:
    record: WatchProfileRecordInput | None = None

    def create_or_replay(self, record: WatchProfileRecordInput):
        self.record = record
        return SimpleNamespace(
            profile_id=record.profile_id,
            version=1,
            state=record.state,
            replayed=False,
        )


def test_service_builds_a_private_canonical_profile_snapshot() -> None:
    repository = CapturingRepository()
    result = WatchProfileService(repository=repository).execute(
        CreateWatchProfileCommand(
            profile_id=PROFILE_ID,
            command_id=COMMAND_ID,
            idempotency_key=IDEMPOTENCY_KEY,
            correlation_id=None,
            tenant_id=TENANT_ID,
            actor_id=ACTOR_ID,
            name="  Gros   œuvre  ",
            criteria=WatchProfileCriteria(
                keywords=("Réhabilitation",),
                project_types=(ProjectType.REFURBISHMENT,),
                included_departments=("59",),
            ),
        )
    )

    assert result.profile_id == PROFILE_ID
    assert repository.record is not None
    assert repository.record.tenant_id == TENANT_ID
    assert repository.record.actor_id == ACTOR_ID
    assert repository.record.name == "Gros œuvre"
    assert repository.record.version == 1
    assert repository.record.criteria_snapshot["keywords"] == ["réhabilitation"]
    assert len(repository.record.criteria_sha256) == 64
    assert "amount" not in str(repository.record.criteria_snapshot).lower()
    assert "price" not in str(repository.record.criteria_snapshot).lower()

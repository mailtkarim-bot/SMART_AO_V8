from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from app.modules.opportunity.application.patron_watch_profile import (
    WatchProfileProjection,
    WatchProfileVersionProjection,
)
from app.modules.opportunity.application.watch_profile_commands import (
    AddOpportunityWatchProfileVersionCommand,
    CreateOpportunityWatchProfileCommand,
)
from app.modules.opportunity.domain.watch_profile import BuyerType, ProjectType, ResponseMode
from pydantic import BaseModel, ConfigDict, Field


class _ClosedContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CreateWatchProfileRequest(_ClosedContract):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    keywords: tuple[str, ...] = ()
    project_types: tuple[ProjectType | str, ...] = ()
    buyer_types: tuple[BuyerType | str, ...] = ()
    included_departments: tuple[str, ...] = ()
    excluded_departments: tuple[str, ...] = ()
    max_radius_km: int | None = Field(default=None, ge=1, le=1_000)
    response_modes: tuple[ResponseMode | str, ...] = ()
    require_qualification: bool = False
    visit_preference: str = Field(default="ANY", pattern=r"^(ANY|PRIORITIZE|REQUIRE)$")

    def to_command(self) -> CreateOpportunityWatchProfileCommand:
        return CreateOpportunityWatchProfileCommand(
            profile_id=uuid5(
                NAMESPACE_URL,
                f"smart-ao:opportunity-watch-profile:{self.command_id}",
            ),
            **self.model_dump(),
        )


class AddWatchProfileVersionRequest(_ClosedContract):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    version_id: UUID
    expected_revision: int = Field(ge=0)
    name: str | None = Field(default=None, max_length=120)
    keywords: tuple[str, ...] = ()
    project_types: tuple[ProjectType | str, ...] = ()
    buyer_types: tuple[BuyerType | str, ...] = ()
    included_departments: tuple[str, ...] = ()
    excluded_departments: tuple[str, ...] = ()
    max_radius_km: int | None = Field(default=None, ge=1, le=1_000)
    response_modes: tuple[ResponseMode | str, ...] = ()
    require_qualification: bool = False
    visit_preference: str = Field(default="ANY", pattern=r"^(ANY|PRIORITIZE|REQUIRE)$")

    def to_command(self, *, profile_id: UUID) -> AddOpportunityWatchProfileVersionCommand:
        return AddOpportunityWatchProfileVersionCommand(
            profile_id=profile_id,
            **self.model_dump(),
        )


class WatchProfileVersionResponse(_ClosedContract):
    version_id: UUID
    version_number: int
    name: str
    criteria: dict[str, object]
    criteria_sha256: str

    @classmethod
    def from_projection(cls, projection: WatchProfileVersionProjection):
        return cls(
            version_id=projection.version_id,
            version_number=projection.version_number,
            name=projection.name,
            criteria=projection.criteria,
            criteria_sha256=projection.criteria_sha256,
        )


class WatchProfileResponse(_ClosedContract):
    profile_id: UUID
    aggregate_revision: int
    current_version: int
    state: str
    versions: list[WatchProfileVersionResponse]

    @classmethod
    def from_projection(cls, projection: WatchProfileProjection):
        return cls(
            profile_id=projection.profile_id,
            aggregate_revision=projection.aggregate_revision,
            current_version=projection.current_version,
            state=projection.state,
            versions=[
                WatchProfileVersionResponse.from_projection(version)
                for version in projection.versions
            ],
        )


class WatchProfileListResponse(_ClosedContract):
    profiles: list[WatchProfileResponse]


class WatchProfileReceiptResponse(_ClosedContract):
    status: str = "SUCCEEDED"
    command_id: UUID
    idempotency_key: UUID
    result_code: str
    aggregate_refs: list[dict[str, object]]
    event_ids: list[UUID]
    replayed: bool

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.modules.opportunity.domain.watch_profile import (
    BuyerType,
    ProjectType,
    ResponseMode,
    WatchProfileCriteria,
)
from app.platform.events.command_contracts import ApplicationCommand


class CreateOpportunityWatchProfileCommand(ApplicationCommand):
    command_type = "CreateOpportunityWatchProfile"

    profile_id: UUID
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

    def criteria(self) -> WatchProfileCriteria:
        return WatchProfileCriteria(
            keywords=self.keywords,
            project_types=tuple(ProjectType(value) for value in self.project_types),
            buyer_types=tuple(BuyerType(value) for value in self.buyer_types),
            included_departments=self.included_departments,
            excluded_departments=self.excluded_departments,
            max_radius_km=self.max_radius_km,
            response_modes=tuple(ResponseMode(value) for value in self.response_modes),
            require_qualification=self.require_qualification,
            visit_preference=self.visit_preference,
        )


class AddOpportunityWatchProfileVersionCommand(ApplicationCommand):
    command_type = "AddOpportunityWatchProfileVersion"

    profile_id: UUID
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

    def criteria(self) -> WatchProfileCriteria:
        return WatchProfileCriteria(
            keywords=self.keywords,
            project_types=tuple(ProjectType(value) for value in self.project_types),
            buyer_types=tuple(BuyerType(value) for value in self.buyer_types),
            included_departments=self.included_departments,
            excluded_departments=self.excluded_departments,
            max_radius_km=self.max_radius_km,
            response_modes=tuple(ResponseMode(value) for value in self.response_modes),
            require_qualification=self.require_qualification,
            visit_preference=self.visit_preference,
        )

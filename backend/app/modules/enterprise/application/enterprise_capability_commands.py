from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.platform.events.command_contracts import ApplicationCommand

CapabilityKind = Literal["QUALIFICATION", "REFERENCE", "EQUIPMENT", "TEAM", "METHOD"]
CapabilityState = Literal["ACTIVE", "SUSPENDED", "RETIRED"]


class CreateEnterpriseCapabilityCommand(ApplicationCommand):
    """Create one patron-owned capability root for the tenant company."""

    command_type = "CreateEnterpriseCapability"

    company_id: UUID
    capability_id: UUID
    capability_kind: CapabilityKind
    name: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=1000)
    state: CapabilityState = "ACTIVE"


class AddEnterpriseCapabilityVersionCommand(ApplicationCommand):
    """Append one immutable capability version and its verified proof links."""

    command_type = "AddEnterpriseCapabilityVersion"

    capability_id: UUID
    version_id: UUID
    expected_revision: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=4000)
    valid_from: datetime
    valid_until: datetime | None = None
    usage_scope: str = Field(min_length=1, max_length=500)
    proof_document_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def validate_dates_and_proofs(self) -> AddEnterpriseCapabilityVersionCommand:
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        if len(set(self.proof_document_ids)) != len(self.proof_document_ids):
            raise ValueError("proof_document_ids must not contain duplicates")
        return self

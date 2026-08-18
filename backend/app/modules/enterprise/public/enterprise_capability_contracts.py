from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field


class EnterpriseCapabilityPublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CreateEnterpriseCapabilityRequest(EnterpriseCapabilityPublicModel):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    capability_kind: Literal["QUALIFICATION", "REFERENCE", "EQUIPMENT", "TEAM", "METHOD"]
    name: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=1000)
    state: Literal["ACTIVE", "SUSPENDED", "RETIRED"] = "ACTIVE"

    def to_command(self, *, company_id: UUID) -> object:
        from app.modules.enterprise.application.enterprise_capability_commands import (
            CreateEnterpriseCapabilityCommand,
        )

        return CreateEnterpriseCapabilityCommand(
            **self.model_dump(),
            company_id=company_id,
            capability_id=uuid5(NAMESPACE_URL, f"enterprise-capability:{self.command_id}"),
        )


class AddEnterpriseCapabilityVersionRequest(EnterpriseCapabilityPublicModel):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    expected_revision: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=4000)
    valid_from: datetime
    valid_until: datetime | None = None
    usage_scope: str = Field(min_length=1, max_length=500)
    proof_document_ids: list[UUID] = Field(default_factory=list, max_length=20)

    def to_command(self, *, capability_id: UUID) -> object:
        from app.modules.enterprise.application.enterprise_capability_commands import (
            AddEnterpriseCapabilityVersionCommand,
        )

        return AddEnterpriseCapabilityVersionCommand(
            **self.model_dump(exclude={"proof_document_ids"}),
            capability_id=capability_id,
            version_id=uuid5(NAMESPACE_URL, f"enterprise-capability-version:{self.command_id}"),
            proof_document_ids=tuple(self.proof_document_ids),
        )


class EnterpriseCapabilityReceiptResponse(EnterpriseCapabilityPublicModel):
    status: Literal["SUCCEEDED"]
    command_id: UUID
    idempotency_key: UUID
    result_code: str
    aggregate_refs: list[dict[str, object]]
    event_ids: list[UUID]
    replayed: bool


class EnterpriseCapabilityVersionResponse(EnterpriseCapabilityPublicModel):
    version_id: UUID
    version_number: int
    title: str
    description: str
    valid_from: datetime
    valid_until: datetime | None
    usage_scope: str
    proof_document_ids: list[UUID]


class EnterpriseCapabilityResponse(EnterpriseCapabilityPublicModel):
    capability_id: UUID
    company_id: UUID
    aggregate_revision: int
    capability_kind: Literal["QUALIFICATION", "REFERENCE", "EQUIPMENT", "TEAM", "METHOD"]
    name: str
    summary: str
    state: Literal["ACTIVE", "SUSPENDED", "RETIRED"]
    versions: list[EnterpriseCapabilityVersionResponse]


class EnterpriseCapabilityListResponse(EnterpriseCapabilityPublicModel):
    capabilities: list[EnterpriseCapabilityResponse]

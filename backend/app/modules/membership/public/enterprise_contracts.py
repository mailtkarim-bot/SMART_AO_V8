from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field


class EnterprisePublicRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EnterprisePublicResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateEnterpriseCompanyRequest(EnterprisePublicRequest):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    legal_name: str = Field(min_length=1, max_length=240)
    trade_name: str | None = Field(default=None, max_length=240)
    siren: str = Field(pattern=r"^[0-9]{9}$")
    siret: str = Field(pattern=r"^[0-9]{14}$")
    vat_number: str = Field(pattern=r"^[A-Z]{2}[A-Z0-9]{2,30}$")
    address_line1: str = Field(min_length=1, max_length=240)
    postal_code: str = Field(min_length=2, max_length=16)
    city: str = Field(min_length=1, max_length=120)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")

    def to_command(self) -> object:
        from app.modules.membership.application.enterprise_commands import (
            CreateEnterpriseCompanyCommand,
        )

        return CreateEnterpriseCompanyCommand(
            **self.model_dump(),
            company_id=uuid5(NAMESPACE_URL, f"enterprise-company:{self.command_id}"),
        )


class RegisterEnterpriseDocumentRequest(EnterprisePublicRequest):
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None = None
    expected_revision: int = Field(ge=0)
    document_kind: Literal["INSURANCE", "KBIS", "RIB"]
    document_label: str = Field(min_length=1, max_length=240)
    storage_object_id: UUID
    original_filename: str = Field(min_length=1, max_length=500)
    issued_at: datetime
    expires_at: datetime | None = None
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verification_status: Literal["PENDING"] = "PENDING"

    def to_command(self, *, company_id: UUID) -> object:
        from app.modules.membership.application.enterprise_commands import (
            RegisterEnterpriseDocumentCommand,
        )

        return RegisterEnterpriseDocumentCommand(
            **self.model_dump(),
            company_id=company_id,
            document_id=uuid5(NAMESPACE_URL, f"enterprise-document:{self.command_id}"),
        )


class EnterpriseReceiptResponse(EnterprisePublicResponse):
    status: Literal["SUCCEEDED"]
    command_id: UUID
    idempotency_key: UUID
    result_code: str
    aggregate_refs: list[dict[str, object]]
    event_ids: list[UUID]
    replayed: bool


class EnterpriseDocumentResponse(EnterprisePublicResponse):
    document_id: UUID
    document_kind: Literal["INSURANCE", "KBIS", "RIB"]
    document_label: str
    issued_at: datetime
    expires_at: datetime | None
    verification_status: Literal["PENDING", "VALIDATED", "EXPIRED", "REJECTED"]


class EnterpriseCompanyResponse(EnterprisePublicResponse):
    company_id: UUID
    aggregate_revision: int = Field(ge=0)
    legal_name: str
    trade_name: str | None
    siren: str
    siret: str
    vat_number: str
    address_line1: str
    postal_code: str
    city: str
    country_code: str
    documents: list[EnterpriseDocumentResponse]

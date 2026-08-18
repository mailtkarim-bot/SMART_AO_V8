from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.platform.events.command_contracts import ApplicationCommand


class CreateEnterpriseCompanyCommand(ApplicationCommand):
    """Create the tenant's patron-owned legal company profile."""

    command_type = "CreateEnterpriseCompany"

    company_id: UUID
    legal_name: str = Field(min_length=1, max_length=240)
    trade_name: str | None = Field(default=None, max_length=240)
    siren: str = Field(pattern=r"^[0-9]{9}$")
    siret: str = Field(pattern=r"^[0-9]{14}$")
    vat_number: str = Field(pattern=r"^[A-Z]{2}[A-Z0-9]{2,30}$")
    address_line1: str = Field(min_length=1, max_length=240)
    postal_code: str = Field(min_length=2, max_length=16)
    city: str = Field(min_length=1, max_length=120)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")


class RegisterEnterpriseDocumentCommand(ApplicationCommand):
    """Register one immutable company proof or banking document."""

    command_type = "RegisterEnterpriseDocument"

    company_id: UUID
    document_id: UUID
    expected_revision: int = Field(ge=0)
    document_kind: Literal["INSURANCE", "KBIS", "RIB"]
    document_label: str = Field(min_length=1, max_length=240)
    storage_object_id: UUID
    original_filename: str = Field(min_length=1, max_length=500)
    issued_at: datetime
    expires_at: datetime | None = None
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verification_status: Literal["PENDING"] = "PENDING"

    @model_validator(mode="after")
    def validate_dates(self) -> RegisterEnterpriseDocumentCommand:
        if self.expires_at is not None and self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be after issued_at")
        if self.document_kind == "RIB" and self.expires_at is not None:
            raise ValueError("RIB documents do not use an expiry date")
        return self

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.modules.enterprise.application.enterprise_commands import (
    CreateEnterpriseCompanyCommand,
    RegisterEnterpriseDocumentCommand,
)
from app.platform.security.capabilities import Capability, capabilities_for
from app.platform.security.context import ActorKind
from pydantic import ValidationError

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def _company_payload() -> dict[str, object]:
    return {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
        "company_id": uuid4(),
        "legal_name": "Bâtiments Karim SAS",
        "trade_name": "SMART BÂTIMENT",
        "siren": "123456789",
        "siret": "12345678900011",
        "vat_number": "FR12123456789",
        "address_line1": "12 rue des Métiers",
        "postal_code": "75001",
        "city": "Paris",
        "country_code": "FR",
    }


def _document_payload(kind: str = "INSURANCE") -> dict[str, object]:
    return {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
        "company_id": uuid4(),
        "document_id": uuid4(),
        "expected_revision": 0,
        "document_kind": kind,
        "document_label": "Attestation responsabilité civile",
        "storage_object_id": uuid4(),
        "original_filename": "attestation-rc.pdf",
        "issued_at": NOW,
        "expires_at": NOW + timedelta(days=365),
        "sha256": "a" * 64,
        "verification_status": "PENDING",
    }


def test_create_company_command_is_closed_and_canonical() -> None:
    command = CreateEnterpriseCompanyCommand(**_company_payload())

    assert command.legal_name == "Bâtiments Karim SAS"
    assert command.country_code == "FR"
    with pytest.raises(ValidationError):
        CreateEnterpriseCompanyCommand(**{**_company_payload(), "tenant_id": uuid4()})


def test_company_command_rejects_invalid_registration_identifiers() -> None:
    with pytest.raises(ValidationError):
        CreateEnterpriseCompanyCommand(**{**_company_payload(), "siren": "123"})
    with pytest.raises(ValidationError):
        CreateEnterpriseCompanyCommand(**{**_company_payload(), "siret": "123456789"})


def test_document_command_accepts_closed_enterprise_document_kinds() -> None:
    for kind in ("INSURANCE", "KBIS", "RIB"):
        payload = _document_payload(kind)
        if kind == "RIB":
            payload["expires_at"] = None
        command = RegisterEnterpriseDocumentCommand(**payload)
        assert command.document_kind == kind


def test_document_command_rejects_expiry_before_issue_and_forbidden_fields() -> None:
    with pytest.raises(ValidationError):
        RegisterEnterpriseDocumentCommand(
            **{
                **_document_payload(),
                "expires_at": NOW - timedelta(days=1),
            }
        )
    with pytest.raises(ValidationError):
        RegisterEnterpriseDocumentCommand(
            **{**_document_payload(), "iban": "FR7612345678901234567890185"}
        )


def test_enterprise_library_capabilities_are_patron_only() -> None:
    patron = capabilities_for(ActorKind.PATRON_ADMIN)
    collaborator = capabilities_for(ActorKind.COLLABORATEUR)

    assert Capability.ENTERPRISE_LIBRARY_READ in patron
    assert Capability.ENTERPRISE_LIBRARY_WRITE in patron
    assert Capability.ENTERPRISE_LIBRARY_READ not in collaborator
    assert Capability.ENTERPRISE_LIBRARY_WRITE not in collaborator

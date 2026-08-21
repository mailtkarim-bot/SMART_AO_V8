from uuid import uuid4

import pytest
from app.modules.pricing.public.import_contracts import (
    CommitPricingImportRequest,
    PricingImportCommitResponse,
    PricingImportPreviewResponse,
)
from pydantic import ValidationError


def _commit_payload() -> dict[str, object]:
    return {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
        "report_id": uuid4(),
        "expected_batch_revision": 1,
        "expected_report_revision": 0,
    }


def test_commit_request_is_closed_and_requires_positive_batch_revision():
    payload = _commit_payload()
    payload["total_minor"] = 12500

    with pytest.raises(ValidationError):
        CommitPricingImportRequest.model_validate(payload)

    payload = _commit_payload()
    payload["expected_batch_revision"] = 0
    with pytest.raises(ValidationError):
        CommitPricingImportRequest.model_validate(payload)


def test_commit_response_contains_only_receipt_and_aggregate_references():
    response = PricingImportCommitResponse(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        result_code="PRICING_IMPORT_COMMITTED",
        aggregate_refs=[
            {
                "aggregate_type": "FinancialReportSnapshot",
                "aggregate_id": uuid4(),
                "aggregate_revision": 1,
            }
        ],
        event_ids=[uuid4()],
        replayed=False,
    )

    dumped = response.model_dump()
    assert dumped["result_code"] == "PRICING_IMPORT_COMMITTED"
    assert {"total_minor", "designation", "unit_price_minor", "source_sha256"}.isdisjoint(
        dumped
    )

    with pytest.raises(ValidationError):
        PricingImportCommitResponse.model_validate({**dumped, "total_minor": 12500})


def test_preview_response_closes_document_kind_and_row_shape():
    payload = {
        "case_id": uuid4(),
        "document_kind": "DPGF",
        "filename": "bordereau.xlsx",
        "row_count": 1,
        "valid_row_count": 1,
        "error_count": 0,
        "total_minor": 12500,
        "rows": [
            {
                "row_number": 2,
                "code": "A-01",
                "designation": "Terrassement",
                "unit": "m2",
                "quantity_decimal": "10",
                "unit_price_minor": 1250,
                "total_minor": 12500,
                "errors": [],
            }
        ],
    }
    response = PricingImportPreviewResponse.model_validate(payload)
    assert response.document_kind == "DPGF"
    assert response.rows[0].total_minor == 12500

    with pytest.raises(ValidationError):
        PricingImportPreviewResponse.model_validate({**payload, "document_kind": "PDF"})

    with pytest.raises(ValidationError):
        PricingImportPreviewResponse.model_validate(
            {**payload, "rows": [{**payload["rows"][0], "row_number": 0}]}
        )

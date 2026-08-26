from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.modules.decision.infrastructure.cctp_pricing_contradiction_reader import (
    SqlAlchemyDecisionCctpPricingContradictionReader,
)


def test_reader_projects_only_explicit_reviewable_contradictions() -> None:
    tenant_id = uuid4()
    case_id = uuid4()
    dce_version_id = uuid4()
    analysis_id = uuid4()
    fragment_id = uuid4()
    batch_id = uuid4()
    session = MagicMock()
    session.scalar.side_effect = [dce_version_id, analysis_id]
    session.execute.side_effect = [
        SimpleNamespace(
            all=lambda: [
                (
                    fragment_id,
                    {"kind": "pdf_page", "page": 12},
                    "Les variantes sont interdites. La variante garde-corps est mesurée en m².",
                )
            ]
        ),
        SimpleNamespace(
            all=lambda: [
                (
                    batch_id,
                    "BPU",
                    4,
                    "02.01",
                    "Variante garde-corps",
                    "ml",
                )
            ]
        ),
    ]
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    reader = SqlAlchemyDecisionCctpPricingContradictionReader(session_factory)

    findings = reader.detect(tenant_id=tenant_id, case_id=case_id, limit=25)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.dce_version_id == dce_version_id
    assert finding.contradiction_type == "VARIANT_PRICING_SCOPE_CONFLICT"
    assert finding.source_locator_label == "CCTP · page 12"
    assert finding.related_document_kind == "BPU"
    assert finding.verification_status == "REVIEW_REQUIRED"
    assert finding.source_start_byte_offset == 0
    assert finding.source_end_byte_offset > finding.source_start_byte_offset
    assert not hasattr(finding, "quantity_decimal")
    assert not hasattr(finding, "unit_price_minor")
    assert not hasattr(finding, "total_minor")

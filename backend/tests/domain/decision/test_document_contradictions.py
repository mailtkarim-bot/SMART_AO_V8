import pytest
from app.modules.decision.domain.document_contradictions import (
    detect_cctp_pricing_contradiction,
)


@pytest.mark.domain
def test_detects_explicit_variant_scope_conflict() -> None:
    result = detect_cctp_pricing_contradiction(
        cctp_text="Les variantes sont interdites pour cette prestation.",
        pricing_code="V-01",
        pricing_designation="Variante revêtement mural",
        pricing_unit="m2",
    )

    assert result is not None
    assert result.contradiction_type == "VARIANT_PRICING_SCOPE_CONFLICT"
    assert result.comparison_basis == "CCTP_VARIANT_PROHIBITION_V1"


@pytest.mark.domain
def test_detects_explicit_cctp_unit_mismatch() -> None:
    result = detect_cctp_pricing_contradiction(
        cctp_text="La fourniture est mesurée en m² dans le CCTP.",
        pricing_code="01.01",
        pricing_designation="Fourniture et pose de panneau",
        pricing_unit="ml",
    )

    assert result is not None
    assert result.contradiction_type == "PRICING_UNIT_MISMATCH"
    assert result.comparison_basis == "CCTP_EXPLICIT_UNIT_V1"


@pytest.mark.domain
def test_same_unit_and_allowed_variant_produce_no_contradiction() -> None:
    assert (
        detect_cctp_pricing_contradiction(
            cctp_text="Une variante peut être proposée, mesurée en m².",
            pricing_code="01.01",
            pricing_designation="Panneau courant",
            pricing_unit="m2",
        )
        is None
    )


@pytest.mark.domain
def test_missing_pricing_unit_does_not_create_unit_contradiction() -> None:
    assert (
        detect_cctp_pricing_contradiction(
            cctp_text="La prestation est mesurée en m².",
            pricing_code="01.01",
            pricing_designation="Panneau courant",
            pricing_unit=None,
        )
        is None
    )

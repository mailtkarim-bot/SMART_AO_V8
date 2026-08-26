import pytest
from app.modules.decision.domain.pricing_crossing import (
    match_cctp_to_pricing_row,
    normalize_crossing_text,
)


@pytest.mark.domain
def test_normalization_is_case_and_accent_insensitive() -> None:
    assert normalize_crossing_text("Béton armé – façade") == "beton arme facade"


@pytest.mark.domain
def test_exact_code_match_has_maximum_score() -> None:
    result = match_cctp_to_pricing_row(
        cctp_text="Le poste BET-001 concerne le béton de structure.",
        code="BET-001",
        designation="Béton de structure",
        unit="m3",
    )

    assert result is not None
    assert result.score_bps == 10_000
    assert result.match_basis == "CODE_EXACT"


@pytest.mark.domain
def test_two_shared_designation_tokens_produce_review_candidate() -> None:
    result = match_cctp_to_pricing_row(
        cctp_text="Fourniture et mise en œuvre de béton armé pour voile porteur, unité m3.",
        code="VOI-001",
        designation="Béton armé voile",
        unit="m3",
    )

    assert result is not None
    assert result.match_basis == "NORMALIZED_TOKEN_OVERLAP_AND_UNIT"
    assert result.score_bps == 10_000


@pytest.mark.domain
def test_single_short_generic_token_is_not_a_match() -> None:
    result = match_cctp_to_pricing_row(
        cctp_text="Le titulaire fournit le lot.",
        code="LOT-001",
        designation="Lot",
        unit="u",
    )

    assert result is None


@pytest.mark.domain
def test_empty_designation_or_cctp_is_not_a_match() -> None:
    assert (
        match_cctp_to_pricing_row(
            cctp_text="",
            code="A-1",
            designation="Béton",
            unit="m3",
        )
        is None
    )
    assert (
        match_cctp_to_pricing_row(
            cctp_text="Béton de structure",
            code=None,
            designation=None,
            unit="m3",
        )
        is None
    )

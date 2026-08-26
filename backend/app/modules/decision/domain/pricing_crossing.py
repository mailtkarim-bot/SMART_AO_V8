from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_TOKEN_PATTERN = re.compile(r"[a-z0-9]{2,}")
_STOPWORDS = frozenset(
    {
        "avec",
        "dans",
        "des",
        "du",
        "les",
        "pour",
        "sur",
        "une",
        "aux",
        "par",
        "et",
        "de",
        "la",
        "le",
        "un",
    }
)


@dataclass(frozen=True, slots=True)
class PricingCrossingMatch:
    """Pure, explainable match; it never represents an automatic decision."""

    score_bps: int
    match_basis: str


def match_cctp_to_pricing_row(
    *,
    cctp_text: str,
    code: str | None,
    designation: str | None,
    unit: str | None,
) -> PricingCrossingMatch | None:
    """Return a deterministic candidate match from CCTP text to one pricing row.

    The function deliberately uses only normalized lexical evidence. It does not
    infer quantities, prices, compliance, or award decisions. Every returned match
    must therefore be displayed as ``REVIEW_REQUIRED`` by its read projection.
    """

    cctp_tokens = _tokens(cctp_text)
    if not cctp_tokens:
        return None

    normalized_code = _normalize(code or "")
    if normalized_code and _contains_code(cctp_text, normalized_code):
        return PricingCrossingMatch(score_bps=10_000, match_basis="CODE_EXACT")

    designation_tokens = _tokens(designation or "")
    if not designation_tokens:
        return None

    shared = cctp_tokens.intersection(designation_tokens)
    if not _is_eligible(shared=shared, designation_tokens=designation_tokens):
        return None

    score_bps = min(10_000, round(10_000 * len(shared) / len(designation_tokens)))
    if unit and _tokens(unit).intersection(cctp_tokens):
        score_bps = min(10_000, score_bps + 500)
        basis = "NORMALIZED_TOKEN_OVERLAP_AND_UNIT"
    else:
        basis = "NORMALIZED_TOKEN_OVERLAP"
    return PricingCrossingMatch(score_bps=score_bps, match_basis=basis)


def normalize_crossing_text(value: str) -> str:
    """Expose the shared normalization rule for deterministic contract tests."""

    return _normalize(value)


def _is_eligible(*, shared: set[str], designation_tokens: set[str]) -> bool:
    if not shared:
        return False
    if len(shared) >= 2:
        return True
    only_token = next(iter(shared))
    return len(designation_tokens) == 1 and len(only_token) >= 6


def _contains_code(text: str, normalized_code: str) -> bool:
    code_tokens = set(_TOKEN_PATTERN.findall(normalized_code))
    return bool(code_tokens) and code_tokens.issubset(_tokens(text))


def _tokens(value: str) -> set[str]:
    return {token for token in _TOKEN_PATTERN.findall(_normalize(value)) if token not in _STOPWORDS}


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_accents)

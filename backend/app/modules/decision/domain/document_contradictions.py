from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentContradictionMatch:
    """One deterministic contradiction candidate requiring human review."""

    contradiction_type: str
    comparison_basis: str


_UNIT_ALIASES = {
    "m2": "M2",
    "m²": "M2",
    "m3": "M3",
    "m³": "M3",
    "ml": "ML",
    "un": "UN",
    "u": "UN",
    "unite": "UN",
    "unites": "UN",
    "kg": "KG",
    "h": "H",
    "forfait": "FORFAIT",
    "ens": "ENS",
}
_UNIT_PATTERN = re.compile(
    r"(?<![a-zà-ÿ])(?:m2|m²|m3|m³|ml|unité?s?|u|kg|h|forfait|ens)(?![a-zà-ÿ])",
    re.IGNORECASE,
)
_VARIANT_PROHIBITION_PATTERN = re.compile(
    r"\b(?:variante(?:s)?|option(?:s)?)\b[^.\n]{0,80}\b(?:interdit(?:e|es)?|exclu(?:e|es)?|non\s+admise?s?|refusée?s?)\b"
    r"|\b(?:interdit(?:e|es)?|exclu(?:e|es)?|non\s+admise?s?|refusée?s?)\b[^.\n]{0,80}\b(?:variante(?:s)?|option(?:s)?)\b",
    re.IGNORECASE,
)
_VARIANT_ROW_PATTERN = re.compile(r"\b(?:variante(?:s)?|option(?:s)?)\b", re.IGNORECASE)


def detect_cctp_pricing_contradiction(
    *,
    cctp_text: str,
    pricing_code: str | None,
    pricing_designation: str | None,
    pricing_unit: str | None,
) -> DocumentContradictionMatch | None:
    """Detect only explicit deterministic scope/unit contradictions."""

    if _VARIANT_PROHIBITION_PATTERN.search(cctp_text) and _VARIANT_ROW_PATTERN.search(
        " ".join(value for value in (pricing_code, pricing_designation) if value)
    ):
        return DocumentContradictionMatch(
            contradiction_type="VARIANT_PRICING_SCOPE_CONFLICT",
            comparison_basis="CCTP_VARIANT_PROHIBITION_V1",
        )

    if pricing_unit:
        cctp_units = {
            _normalize_unit(match.group(0)) for match in _UNIT_PATTERN.finditer(cctp_text)
        }
        normalized_pricing_unit = _normalize_unit(pricing_unit)
        incompatible_units = cctp_units - {normalized_pricing_unit}
        if incompatible_units:
            return DocumentContradictionMatch(
                contradiction_type="PRICING_UNIT_MISMATCH",
                comparison_basis="CCTP_EXPLICIT_UNIT_V1",
            )
    return None


def _normalize_unit(value: str) -> str:
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )
    return _UNIT_ALIASES.get(normalized.strip(), normalized.strip().upper())

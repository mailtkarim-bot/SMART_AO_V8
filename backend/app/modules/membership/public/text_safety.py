"""Public, framework-free text safety contract for collaborator-facing content."""

from __future__ import annotations

import re

_FORBIDDEN_FINANCIAL_TERMS = re.compile(
    r"\b(price|prix|cost|coût|cout|margin|marge|treasury|trésorerie|tresorerie|"
    r"financial|financier|finance|go/no-go|go_no_go|deposit|dépôt|depot|"
    r"submission|soumission|chiffrage)\b",
    re.IGNORECASE,
)


def contains_forbidden_text(*values: str) -> bool:
    """Return whether collaborator-facing text contains financial terms."""

    return any(_FORBIDDEN_FINANCIAL_TERMS.search(value) for value in values)

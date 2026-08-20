"""Runtime database configuration helpers used by Alembic."""

from __future__ import annotations

import os
from collections.abc import Mapping

_RUNTIME_DATABASE_URL = "SMART_AO_DATABASE_URL"
_PLACEHOLDER_PREFIX = "REPLACE_WITH_"


def resolve_database_url(
    configured_url: str,
    environment: Mapping[str, str] | None = None,
) -> str:
    """Prefer the injected runtime URL while retaining local Alembic defaults."""

    source = os.environ if environment is None else environment
    runtime_url = source.get(_RUNTIME_DATABASE_URL, "").strip()
    if runtime_url and not runtime_url.startswith(_PLACEHOLDER_PREFIX):
        return runtime_url
    return configured_url

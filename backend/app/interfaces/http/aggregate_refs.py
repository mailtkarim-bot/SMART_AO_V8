"""Validation helpers for aggregate references returned by application services."""


def require_aggregate_revision(value: object) -> int:
    """Return a non-negative integer revision or fail closed on malformed data."""

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("INVALID_AGGREGATE_REVISION")
    return value

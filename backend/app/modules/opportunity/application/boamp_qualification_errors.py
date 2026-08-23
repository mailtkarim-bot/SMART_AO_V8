"""Application-level errors for the BOAMP qualification use case."""

from __future__ import annotations


class BoampQualificationIdempotencyConflict(RuntimeError):
    """The qualification identity was reused for incompatible data."""

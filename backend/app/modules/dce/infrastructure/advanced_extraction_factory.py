"""Composition root for optional local DCE extraction adapters."""

from app.modules.dce.application.extraction import AdvancedDocumentExtractionPort
from app.modules.dce.infrastructure.advanced_extraction import (
    CompositeAdvancedDocumentExtractionAdapter,
)
from app.modules.dce.infrastructure.advanced_extraction import (
    build_advanced_extractor_from_environment as _build_advanced_extractor,
)


def build_advanced_extractor_from_environment() -> AdvancedDocumentExtractionPort | None:
    """Build only when explicitly enabled; OCR has its own separate opt-in."""

    return _build_advanced_extractor()


__all__ = [
    "CompositeAdvancedDocumentExtractionAdapter",
    "build_advanced_extractor_from_environment",
]

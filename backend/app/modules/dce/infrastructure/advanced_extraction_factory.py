from __future__ import annotations

import os

from app.modules.dce.application.extraction import AdvancedDocumentExtractionPort
from app.modules.dce.infrastructure.advanced_extraction import (
    DoclingAdvancedExtractionAdapter,
    PyMuPdfAdvancedExtractionAdapter,
)


class CompositeAdvancedDocumentExtractionAdapter:
    """Select the narrowest local adapter for each media type."""

    def __init__(self) -> None:
        self._pdf = PyMuPdfAdvancedExtractionAdapter()
        self._docling = DoclingAdvancedExtractionAdapter()

    def extract(self, *, media_type: str, source_bytes: bytes):
        if media_type == "application/pdf":
            return self._pdf.extract(media_type=media_type, source_bytes=source_bytes)
        return self._docling.extract(media_type=media_type, source_bytes=source_bytes)


def build_advanced_extractor_from_environment() -> AdvancedDocumentExtractionPort | None:
    """Build only when explicitly enabled; default extraction remains deterministic."""

    if os.getenv("SMART_AO_ADVANCED_EXTRACTION_ENABLED", "0") != "1":
        return None
    return CompositeAdvancedDocumentExtractionAdapter()

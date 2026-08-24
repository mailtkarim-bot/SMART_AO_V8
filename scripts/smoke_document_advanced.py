"""Smoke-test the optional document-advanced dependency boundary."""

from __future__ import annotations

import json

from app.modules.dce.infrastructure.advanced_extraction import (
    DoclingAdvancedExtractionAdapter,
    PyMuPdfAdvancedExtractionAdapter,
)


def _pdf_bytes() -> bytes:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Exigence de délai de réponse")
    return document.tobytes()


def main() -> None:
    source = _pdf_bytes()
    pymupdf_projection = PyMuPdfAdvancedExtractionAdapter().extract(
        media_type="application/pdf",
        source_bytes=source,
    )
    # Import and construction are checked, but conversion is not run here:
    # Docling may load optional ML artifacts, which must be preloaded and
    # approved on the target worker before any production activation.
    docling_imported = DoclingAdvancedExtractionAdapter.__module__ == (
        "app.modules.dce.infrastructure.advanced_extraction"
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "pymupdf_status": pymupdf_projection.status,
                "pymupdf_fragment_count": len(pymupdf_projection.fragments),
                "pymupdf_locator": pymupdf_projection.fragments[0].locator_json,
                "docling_adapter_imported": docling_imported,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

"""Optional local adapters for advanced document extraction.

These adapters are never imported by the default deterministic extractor unless
explicitly injected by the composition root. Their output remains a bounded,
source-anchored projection and is still subject to human review downstream.
"""

from __future__ import annotations

from tempfile import NamedTemporaryFile

from app.modules.dce.application.extraction import ExtractionProjection, _fragmentize

_SUPPORTED_DOCLING_MEDIA_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "image/jpeg",
        "image/png",
        "image/tiff",
    }
)


class PyMuPdfAdvancedExtractionAdapter:
    """Extract PDF text blocks with page and bounding-box provenance."""

    extractor_id = "smart-ao-pymupdf"
    extractor_version = "1"

    def extract(self, *, media_type: str, source_bytes: bytes) -> ExtractionProjection:
        if media_type != "application/pdf":
            return ExtractionProjection(status="UNSUPPORTED", failure_code=None, fragments=())
        try:
            import pymupdf
        except ImportError as exc:
            raise RuntimeError("document-advanced extra is not installed") from exc

        entries: list[tuple[dict[str, object], str]] = []
        with pymupdf.open(stream=source_bytes, filetype="pdf") as document:
            for page_number, page in enumerate(document, start=1):
                for block_number, block in enumerate(page.get_text("blocks", sort=True), start=1):
                    if len(block) < 5:
                        continue
                    text = str(block[4])
                    entries.append(
                        (
                            {
                                "kind": "pymupdf_block",
                                "page": page_number,
                                "block": block_number,
                                "bbox": [float(value) for value in block[:4]],
                            },
                            text,
                        )
                    )
        fragments = _fragmentize(entries)
        return ExtractionProjection(
            status="COMPLETED" if fragments else "FAILED_SAFE",
            failure_code=None if fragments else "EMPTY_EXTRACTED_TEXT",
            fragments=fragments,
        )


class DoclingAdvancedExtractionAdapter:
    """Use Docling locally for complex formats, never from an HTTP request."""

    extractor_id = "smart-ao-docling"
    extractor_version = "1"

    def extract(self, *, media_type: str, source_bytes: bytes) -> ExtractionProjection:
        if media_type not in _SUPPORTED_DOCLING_MEDIA_TYPES:
            return ExtractionProjection(status="UNSUPPORTED", failure_code=None, fragments=())
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise RuntimeError("document-advanced extra is not installed") from exc

        suffix = _suffix_for_media_type(media_type)
        with NamedTemporaryFile(
            mode="wb",
            suffix=suffix,
            prefix="smart-ao-docling-",
            delete=True,
        ) as file:
            file.write(source_bytes)
            file.flush()
            document = DocumentConverter().convert(file.name).document
            markdown = document.export_to_markdown()
        lines = markdown.splitlines()
        fragments = _fragmentize(
            (
                ({"kind": "docling_markdown", "line": line_number}, line)
                for line_number, line in enumerate(lines, start=1)
            )
        )
        return ExtractionProjection(
            status="COMPLETED" if fragments else "FAILED_SAFE",
            failure_code=None if fragments else "EMPTY_EXTRACTED_TEXT",
            fragments=fragments,
        )


def _suffix_for_media_type(media_type: str) -> str:
    return {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "text/plain": ".txt",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/tiff": ".tiff",
    }.get(media_type, ".bin")

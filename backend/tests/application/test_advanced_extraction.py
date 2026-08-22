from __future__ import annotations

import sys
from types import ModuleType

from app.modules.dce.application.extraction import ExtractionProjection, _project_document
from app.modules.dce.infrastructure.advanced_extraction import (
    DoclingAdvancedExtractionAdapter,
    PyMuPdfAdvancedExtractionAdapter,
)


def test_advanced_extractor_falls_back_to_deterministic_for_unsupported_media() -> None:
    class UnsupportedAdapter:
        def extract(self, *, media_type: str, source_bytes: bytes) -> ExtractionProjection:
            return ExtractionProjection(status="UNSUPPORTED", failure_code=None, fragments=())

    projection = _project_document(
        media_type="text/plain",
        source_bytes=b"ligne source",
        advanced_extractor=UnsupportedAdapter(),
    )

    assert projection.status == "COMPLETED"
    assert projection.fragments[0].locator_json["kind"] == "text_line"


def test_pymupdf_adapter_preserves_page_block_and_bbox(monkeypatch) -> None:
    class FakePage:
        def get_text(self, mode: str, sort: bool):
            assert mode == "blocks"
            assert sort is True
            return [(1, 2, 30, 40, "texte PDF\n", 0, 0)]

    class FakeDocument:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def __iter__(self):
            return iter([FakePage()])

    fake_pymupdf = ModuleType("pymupdf")
    fake_pymupdf.open = lambda *, stream, filetype: FakeDocument()
    monkeypatch.setitem(sys.modules, "pymupdf", fake_pymupdf)

    projection = PyMuPdfAdvancedExtractionAdapter().extract(
        media_type="application/pdf",
        source_bytes=b"pdf",
    )

    assert projection.status == "COMPLETED"
    assert projection.fragments[0].locator_json == {
        "kind": "pymupdf_block",
        "page": 1,
        "block": 1,
        "bbox": [1.0, 2.0, 30.0, 40.0],
        "part": 1,
    }


def test_docling_adapter_uses_local_temp_file_and_exports_markdown(monkeypatch) -> None:
    calls: list[str] = []

    class FakeDoclingDocument:
        def export_to_markdown(self) -> str:
            return "# Titre\n\nExigence"

    class FakeConversion:
        document = FakeDoclingDocument()

    class FakeConverter:
        def convert(self, source: str):
            calls.append(source)
            return FakeConversion()

    fake_docling_converter = ModuleType("docling.document_converter")
    fake_docling_converter.DocumentConverter = FakeConverter
    fake_docling = ModuleType("docling")
    monkeypatch.setitem(sys.modules, "docling", fake_docling)
    monkeypatch.setitem(sys.modules, "docling.document_converter", fake_docling_converter)

    projection = DoclingAdvancedExtractionAdapter().extract(
        media_type="application/pdf",
        source_bytes=b"pdf",
    )

    assert projection.status == "COMPLETED"
    assert len(calls) == 1
    assert calls[0].endswith(".pdf")
    assert projection.fragments[0].locator_json["kind"] == "docling_markdown"
    assert projection.fragments[1].locator_json["line"] == 3

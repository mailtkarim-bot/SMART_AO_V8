from __future__ import annotations

import sys
from types import ModuleType

import pytest
from app.modules.dce.application.commands import (
    DceExtractionFragmentInput,
    RecordDceDocumentExtractionCommand,
)
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


def test_native_projection_has_priority_over_ocr_fallback() -> None:
    class MustNotRunAdapter:
        def extract(self, *, media_type: str, source_bytes: bytes) -> ExtractionProjection:
            raise AssertionError("advanced adapter must not run for native text")

    projection = _project_document(
        media_type="text/plain",
        source_bytes=b"texte natif",
        advanced_extractor=MustNotRunAdapter(),
    )

    assert projection.status == "COMPLETED"
    assert projection.fragments[0].text == "texte natif"


def test_rapidocr_requires_preloaded_local_models() -> None:
    from app.modules.dce.infrastructure.advanced_extraction import RapidOcrAdvancedExtractionAdapter

    called = False

    def engine_factory(_paths: dict[str, str]):
        nonlocal called
        called = True
        raise AssertionError("engine must not initialize without model files")

    projection = RapidOcrAdvancedExtractionAdapter(engine_factory=engine_factory).extract(
        media_type="image/png",
        source_bytes=b"not an image",
    )

    assert projection.status == "FAILED_SAFE"
    assert projection.failure_code == "OCR_MODELS_REQUIRED"
    assert projection.fragments == ()
    assert called is False


def test_rapidocr_projection_is_review_required_and_source_anchored(tmp_path) -> None:
    from io import BytesIO
    from types import SimpleNamespace

    from app.modules.dce.infrastructure.advanced_extraction import RapidOcrAdvancedExtractionAdapter
    from PIL import Image

    model_paths = {}
    for name in ("det", "cls", "rec"):
        path = tmp_path / f"{name}.onnx"
        path.write_bytes(b"fixture model placeholder")
        model_paths[name] = str(path)
    keys_path = tmp_path / "ppocr_keys.txt"
    keys_path.write_text("a\nb\n", encoding="utf-8")

    def engine_factory(paths: dict[str, str]):
        assert paths["Det.model_path"] == model_paths["det"]
        assert paths["Cls.model_path"] == model_paths["cls"]
        assert paths["Rec.model_path"] == model_paths["rec"]
        assert paths["Rec.rec_keys_path"] == str(keys_path)
        return lambda _image: SimpleNamespace(
            txts=["Texte scanné"],
            boxes=[[[1, 2], [31, 2], [31, 12], [1, 12]]],
        )

    image_buffer = BytesIO()
    Image.new("RGB", (64, 32), "white").save(image_buffer, format="PNG")
    projection = RapidOcrAdvancedExtractionAdapter(
        det_model_path=model_paths["det"],
        cls_model_path=model_paths["cls"],
        rec_model_path=model_paths["rec"],
        rec_keys_path=str(keys_path),
        engine_factory=engine_factory,
    ).extract(media_type="image/png", source_bytes=image_buffer.getvalue())

    assert projection.status == "REVIEW_REQUIRED"
    assert projection.failure_code == "OCR_HUMAN_REVIEW_REQUIRED"
    assert projection.extractor_id == "smart-ao-rapidocr"
    assert projection.fragments[0].locator_json == {
        "kind": "ocr_page",
        "page": 1,
        "order": 1,
        "bbox": [[1.0, 2.0], [31.0, 2.0], [31.0, 12.0], [1.0, 12.0]],
        "part": 1,
    }


def test_rapidocr_rejects_page_pixel_limit(monkeypatch, tmp_path) -> None:
    from io import BytesIO
    from types import SimpleNamespace

    from app.modules.dce.infrastructure.advanced_extraction import (
        RapidOcrAdvancedExtractionAdapter,
    )
    from PIL import Image

    model_paths = []
    for name in ("det", "cls", "rec"):
        path = tmp_path / f"{name}.onnx"
        path.write_bytes(b"fixture model placeholder")
        model_paths.append(str(path))
    keys_path = tmp_path / "ppocr_keys.txt"
    keys_path.write_text("a\nb\n", encoding="utf-8")

    image_buffer = BytesIO()
    Image.new("RGB", (64, 32), "white").save(image_buffer, format="PNG")
    monkeypatch.setattr(
        "app.modules.dce.infrastructure.advanced_extraction.MAX_OCR_PIXELS_PER_PAGE",
        1,
    )
    projection = RapidOcrAdvancedExtractionAdapter(
        det_model_path=model_paths[0],
        cls_model_path=model_paths[1],
        rec_model_path=model_paths[2],
        rec_keys_path=str(keys_path),
        engine_factory=lambda _paths: lambda _image: SimpleNamespace(txts=["texte"], boxes=[]),
    ).extract(media_type="image/png", source_bytes=image_buffer.getvalue())

    assert projection.status == "REJECTED_LIMIT"
    assert projection.failure_code == "OCR_EXTRACTION_LIMIT"
    assert projection.fragments == ()


def test_review_required_extraction_command_requires_bounded_fragments() -> None:
    from hashlib import sha256
    from uuid import uuid4

    fragment_text = "Texte OCR soumis à revue"
    fragment = DceExtractionFragmentInput(
        ordinal=1,
        locator_json={"kind": "ocr_page", "page": 1, "order": 1},
        text=fragment_text,
        text_sha256=sha256(fragment_text.encode("utf-8")).hexdigest(),
    )
    command = RecordDceDocumentExtractionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        extraction_id=uuid4(),
        dce_document_id=uuid4(),
        input_sha256="a" * 64,
        extractor_id="smart-ao-rapidocr",
        extractor_version="1",
        status="REVIEW_REQUIRED",
        extracted_char_count=len(fragment_text),
        failure_code="OCR_HUMAN_REVIEW_REQUIRED",
        fragments=[fragment],
    )

    assert command.status == "REVIEW_REQUIRED"
    assert command.fragments[0].locator_json["kind"] == "ocr_page"
    with pytest.raises(ValueError, match="review-required extraction requires fragments"):
        RecordDceDocumentExtractionCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            extraction_id=uuid4(),
            dce_document_id=uuid4(),
            input_sha256="a" * 64,
            extractor_id="smart-ao-rapidocr",
            extractor_version="1",
            status="REVIEW_REQUIRED",
            extracted_char_count=0,
            failure_code="OCR_HUMAN_REVIEW_REQUIRED",
            fragments=[],
        )


def test_ocr_factory_is_disabled_by_default_and_separate_from_advanced(monkeypatch) -> None:
    from app.modules.dce.infrastructure.advanced_extraction_factory import (
        build_advanced_extractor_from_environment,
    )

    monkeypatch.delenv("SMART_AO_ADVANCED_EXTRACTION_ENABLED", raising=False)
    monkeypatch.delenv("SMART_AO_OCR_ENABLED", raising=False)
    assert build_advanced_extractor_from_environment() is None

    monkeypatch.setenv("SMART_AO_OCR_ENABLED", "1")
    adapter = build_advanced_extractor_from_environment()
    assert adapter is not None
    assert type(adapter).__name__ == "CompositeAdvancedDocumentExtractionAdapter"

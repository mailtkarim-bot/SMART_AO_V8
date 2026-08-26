"""Optional local adapters for bounded, source-anchored DCE extraction."""

from __future__ import annotations

import math
import os
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from app.modules.dce.application.extraction import (
    ExtractionLimitError,
    ExtractionProjection,
    _fragmentize,
)

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
_SUPPORTED_OCR_MEDIA_TYPES = frozenset({"application/pdf", "image/jpeg", "image/png", "image/tiff"})
MAX_OCR_PAGES = 200
MAX_OCR_PIXELS_PER_PAGE = 25_000_000
MAX_OCR_TOTAL_PIXELS = 250_000_000
DEFAULT_OCR_DPI = 150
MIN_OCR_DPI = 72
MAX_OCR_DPI = 300


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
            if hasattr(document, "__len__") and len(document) > 2_000:
                raise ExtractionLimitError
            for page_number, page in enumerate(document, start=1):
                for block_number, block in enumerate(page.get_text("blocks", sort=True), start=1):
                    if len(block) < 5:
                        continue
                    entries.append(
                        (
                            {
                                "kind": "pymupdf_block",
                                "page": page_number,
                                "block": block_number,
                                "bbox": [float(value) for value in block[:4]],
                            },
                            str(block[4]),
                        )
                    )
        fragments = _fragmentize(entries)
        return ExtractionProjection(
            status="COMPLETED" if fragments else "FAILED_SAFE",
            failure_code=None if fragments else "EMPTY_EXTRACTED_TEXT",
            fragments=fragments,
            extractor_id=self.extractor_id,
            extractor_version=self.extractor_version,
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
        with NamedTemporaryFile(
            mode="wb", suffix=_suffix_for_media_type(media_type), delete=True
        ) as file:
            file.write(source_bytes)
            file.flush()
            markdown = DocumentConverter().convert(file.name).document.export_to_markdown()
        fragments = _fragmentize(
            ({"kind": "docling_markdown", "line": line_number}, line)
            for line_number, line in enumerate(markdown.splitlines(), start=1)
        )
        return ExtractionProjection(
            status="COMPLETED" if fragments else "FAILED_SAFE",
            failure_code=None if fragments else "EMPTY_EXTRACTED_TEXT",
            fragments=fragments,
            extractor_id=self.extractor_id,
            extractor_version=self.extractor_version,
        )


class RapidOcrAdvancedExtractionAdapter:
    """Run RapidOCR only with an explicitly configured local runtime and models."""

    extractor_id = "smart-ao-rapidocr"
    extractor_version = "1"

    def __init__(
        self,
        *,
        det_model_path: str | None = None,
        cls_model_path: str | None = None,
        rec_model_path: str | None = None,
        rec_keys_path: str | None = None,
        dpi: int = DEFAULT_OCR_DPI,
        engine_factory: Callable[[dict[str, str]], Any] | None = None,
    ) -> None:
        self._model_paths = {
            "Det.model_path": det_model_path or "",
            "Cls.model_path": cls_model_path or "",
            "Rec.model_path": rec_model_path or "",
            "Rec.rec_keys_path": rec_keys_path or "",
        }
        self._dpi = max(MIN_OCR_DPI, min(MAX_OCR_DPI, dpi))
        self._engine_factory = engine_factory
        self._engine: Any | None = None
        self._engine_error: str | None = None

    def extract(self, *, media_type: str, source_bytes: bytes) -> ExtractionProjection:
        if media_type not in _SUPPORTED_OCR_MEDIA_TYPES:
            return ExtractionProjection(status="UNSUPPORTED", failure_code=None, fragments=())
        engine = self._get_engine()
        if engine is None:
            return self._failed(
                "OCR_MODELS_REQUIRED"
                if self._engine_error == "OCR_MODEL_PATHS_REQUIRED"
                else "OCR_RUNTIME_UNAVAILABLE"
            )
        try:
            entries = self._extract_entries(
                media_type=media_type, source_bytes=source_bytes, engine=engine
            )
            fragments = _fragmentize(entries)
        except ExtractionLimitError:
            return self._failed("OCR_EXTRACTION_LIMIT", status="REJECTED_LIMIT")
        except (OSError, ValueError, RuntimeError, ImportError) as error:
            self._engine_error = type(error).__name__
            return self._failed("OCR_RUNTIME_FAILED")
        except Exception as error:
            self._engine_error = type(error).__name__
            return self._failed("OCR_RUNTIME_FAILED")
        if not fragments:
            return self._failed("OCR_EMPTY_TEXT")
        return ExtractionProjection(
            status="REVIEW_REQUIRED",
            failure_code="OCR_HUMAN_REVIEW_REQUIRED",
            fragments=fragments,
            extractor_id=self.extractor_id,
            extractor_version=self.extractor_version,
        )

    def _get_engine(self) -> Any | None:
        if self._engine is not None or self._engine_error is not None:
            return self._engine
        if not all(Path(path).is_file() for path in self._model_paths.values()):
            self._engine_error = "OCR_MODEL_PATHS_REQUIRED"
            return None
        try:
            if self._engine_factory is not None:
                self._engine = self._engine_factory(dict(self._model_paths))
            else:
                from rapidocr import RapidOCR

                self._engine = RapidOCR(params=dict(self._model_paths))
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            self._engine_error = type(error).__name__
            return None
        return self._engine

    def _extract_entries(
        self, *, media_type: str, source_bytes: bytes, engine: Any
    ) -> list[tuple[dict[str, object], str]]:
        if media_type == "application/pdf":
            return self._extract_pdf_entries(source_bytes=source_bytes, engine=engine)
        return self._extract_image_entries(
            source_bytes=source_bytes, media_type=media_type, engine=engine
        )

    def _extract_pdf_entries(
        self, *, source_bytes: bytes, engine: Any
    ) -> list[tuple[dict[str, object], str]]:
        try:
            import numpy as np
            import pymupdf
        except ImportError as exc:
            raise RuntimeError("OCR PDF rendering dependencies are not installed") from exc
        entries: list[tuple[dict[str, object], str]] = []
        total_pixels = 0
        with pymupdf.open(stream=source_bytes, filetype="pdf") as document:
            if hasattr(document, "__len__") and len(document) > MAX_OCR_PAGES:
                raise ExtractionLimitError
            matrix = pymupdf.Matrix(self._dpi / 72.0, self._dpi / 72.0)
            for page_number, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                page_pixels = pixmap.width * pixmap.height
                if page_pixels > MAX_OCR_PIXELS_PER_PAGE:
                    raise ExtractionLimitError
                total_pixels += page_pixels
                if total_pixels > MAX_OCR_TOTAL_PIXELS:
                    raise ExtractionLimitError
                image: Any = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                    pixmap.height, pixmap.width, pixmap.n
                )
                entries.extend(
                    self._recognize_page(
                        image=image,
                        page_number=page_number,
                        width=pixmap.width,
                        height=pixmap.height,
                        engine=engine,
                    )
                )
        return entries

    def _extract_image_entries(
        self, *, source_bytes: bytes, media_type: str, engine: Any
    ) -> list[tuple[dict[str, object], str]]:
        try:
            import numpy as np
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("OCR image dependencies are not installed") from exc
        try:
            with Image.open(BytesIO(source_bytes)) as image:
                image.load()
                width, height = image.size
                if width * height > MAX_OCR_PIXELS_PER_PAGE:
                    raise ExtractionLimitError
                return self._recognize_page(
                    image=np.asarray(image.convert("RGB")),
                    page_number=1,
                    width=width,
                    height=height,
                    engine=engine,
                )
        except ExtractionLimitError:
            raise
        except (OSError, ValueError) as error:
            raise RuntimeError(f"invalid OCR image {media_type}") from error

    def _recognize_page(
        self, *, image: Any, page_number: int, width: int, height: int, engine: Any
    ) -> list[tuple[dict[str, object], str]]:
        result = engine(image)
        texts = getattr(result, "txts", None) or []
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            boxes = []
        entries: list[tuple[dict[str, object], str]] = []
        for order, text in enumerate(texts, start=1):
            normalized = str(text).strip()
            if not normalized:
                continue
            locator: dict[str, object] = {"kind": "ocr_page", "page": page_number, "order": order}
            if order <= len(boxes):
                bbox = _safe_bbox(boxes[order - 1], width=width, height=height)
                if bbox is not None:
                    locator["bbox"] = bbox
            entries.append((locator, normalized))
        return entries

    def _failed(self, code: str, *, status: str = "FAILED_SAFE") -> ExtractionProjection:
        return ExtractionProjection(
            status=status,
            failure_code=code,
            fragments=(),
            extractor_id=self.extractor_id,
            extractor_version=self.extractor_version,
        )


def _safe_bbox(value: Any, *, width: int, height: int) -> list[list[float]] | None:
    try:
        points = [[float(point[0]), float(point[1])] for point in value]
    except (TypeError, ValueError, IndexError):
        return None
    if len(points) != 4 or any(
        not math.isfinite(coordinate) for point in points for coordinate in point
    ):
        return None
    if any(
        coordinate < 0 or coordinate > limit
        for point in points
        for coordinate, limit in zip(point, (width, height), strict=True)
    ):
        return None
    return points


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


def build_rapidocr_adapter_from_environment() -> RapidOcrAdvancedExtractionAdapter:
    try:
        dpi = int(os.getenv("SMART_AO_OCR_DPI", str(DEFAULT_OCR_DPI)))
    except ValueError:
        dpi = DEFAULT_OCR_DPI
    return RapidOcrAdvancedExtractionAdapter(
        det_model_path=os.getenv("SMART_AO_OCR_DET_MODEL_PATH"),
        cls_model_path=os.getenv("SMART_AO_OCR_CLS_MODEL_PATH"),
        rec_model_path=os.getenv("SMART_AO_OCR_REC_MODEL_PATH"),
        rec_keys_path=os.getenv("SMART_AO_OCR_REC_KEYS_PATH"),
        dpi=dpi,
    )


class CompositeAdvancedDocumentExtractionAdapter:
    """Select native advanced parsing first, then optional OCR for image-only input."""

    def __init__(self, *, ocr_enabled: bool = False) -> None:
        self._pdf = PyMuPdfAdvancedExtractionAdapter()
        self._docling = DoclingAdvancedExtractionAdapter()
        self._ocr = build_rapidocr_adapter_from_environment() if ocr_enabled else None

    def extract(self, *, media_type: str, source_bytes: bytes) -> ExtractionProjection:
        if media_type == "application/pdf":
            native = self._pdf.extract(media_type=media_type, source_bytes=source_bytes)
            if native.status == "COMPLETED" or self._ocr is None:
                return native
            return self._ocr.extract(media_type=media_type, source_bytes=source_bytes)
        if self._ocr is not None and media_type in _SUPPORTED_OCR_MEDIA_TYPES:
            return self._ocr.extract(media_type=media_type, source_bytes=source_bytes)
        return self._docling.extract(media_type=media_type, source_bytes=source_bytes)


def build_advanced_extractor_from_environment() -> Any | None:
    advanced_enabled = os.getenv("SMART_AO_ADVANCED_EXTRACTION_ENABLED", "0") == "1"
    ocr_enabled = os.getenv("SMART_AO_OCR_ENABLED", "0") == "1"
    if not advanced_enabled and not ocr_enabled:
        return None
    return CompositeAdvancedDocumentExtractionAdapter(ocr_enabled=ocr_enabled)

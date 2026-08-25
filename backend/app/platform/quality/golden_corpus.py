from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_ALLOWED_MEDIA_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
)


@dataclass(frozen=True, slots=True)
class GoldenDocument:
    document_id: str
    filename: str
    sha256: str
    media_type: str
    expected_text_fragments: tuple[str, ...]
    expected_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GoldenCorpusManifest:
    schema_version: int
    corpus_id: str
    documents: tuple[GoldenDocument, ...]


def load_manifest(path: Path) -> GoldenCorpusManifest:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("GOLDEN_MANIFEST_INVALID_JSON") from error
    return parse_manifest(raw)


def parse_manifest(raw: Any) -> GoldenCorpusManifest:
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "corpus_id", "documents"}:
        raise ValueError("GOLDEN_MANIFEST_FIELDS_INVALID")
    if (
        raw["schema_version"] != 1
        or not isinstance(raw["corpus_id"], str)
        or not raw["corpus_id"].strip()
    ):
        raise ValueError("GOLDEN_MANIFEST_HEADER_INVALID")
    documents = raw["documents"]
    if not isinstance(documents, list):
        raise ValueError("GOLDEN_MANIFEST_DOCUMENTS_INVALID")
    parsed: list[GoldenDocument] = []
    seen_ids: set[str] = set()
    for item in documents:
        document = _parse_document(item)
        if document.document_id in seen_ids:
            raise ValueError("GOLDEN_MANIFEST_DOCUMENT_ID_DUPLICATE")
        seen_ids.add(document.document_id)
        parsed.append(document)
    return GoldenCorpusManifest(
        schema_version=1,
        corpus_id=raw["corpus_id"].strip(),
        documents=tuple(parsed),
    )


def _parse_document(raw: Any) -> GoldenDocument:
    required = {
        "document_id",
        "filename",
        "sha256",
        "media_type",
        "expected_text_fragments",
        "expected_labels",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise ValueError("GOLDEN_DOCUMENT_FIELDS_INVALID")
    values = {key: raw[key] for key in required}
    document_id = _non_empty(values["document_id"], "GOLDEN_DOCUMENT_ID_INVALID")
    filename = _safe_filename(values["filename"])
    sha256 = _non_empty(values["sha256"], "GOLDEN_DOCUMENT_HASH_INVALID")
    if not _SHA256_RE.fullmatch(sha256):
        raise ValueError("GOLDEN_DOCUMENT_HASH_INVALID")
    media_type = _non_empty(values["media_type"], "GOLDEN_DOCUMENT_MEDIA_TYPE_INVALID")
    if media_type not in _ALLOWED_MEDIA_TYPES:
        raise ValueError("GOLDEN_DOCUMENT_MEDIA_TYPE_INVALID")
    return GoldenDocument(
        document_id=document_id,
        filename=filename,
        sha256=sha256,
        media_type=media_type,
        expected_text_fragments=_string_tuple(
            values["expected_text_fragments"], "GOLDEN_EXPECTED_TEXT_INVALID"
        ),
        expected_labels=_string_tuple(values["expected_labels"], "GOLDEN_EXPECTED_LABELS_INVALID"),
    )


def _non_empty(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(code)
    return value.strip()


def _safe_filename(value: Any) -> str:
    filename = _non_empty(value, "GOLDEN_DOCUMENT_FILENAME_INVALID")
    path = Path(filename)
    if path.is_absolute() or path.name != filename or ".." in path.parts:
        raise ValueError("GOLDEN_DOCUMENT_FILENAME_INVALID")
    return filename


def _string_tuple(value: Any, code: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(code)
    return tuple(item.strip() for item in value)


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    if len(arguments) != 1:
        print("usage: python -m app.platform.quality.golden_corpus MANIFEST.json", file=sys.stderr)
        return 2
    try:
        manifest = load_manifest(Path(arguments[0]))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"valid corpus={manifest.corpus_id} documents={len(manifest.documents)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

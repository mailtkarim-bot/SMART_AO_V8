from __future__ import annotations

import pytest
from app.platform.quality.golden_corpus import parse_manifest


def _manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "corpus_id": "corpus-v1",
        "documents": [
            {
                "document_id": "dce-001",
                "filename": "rc.pdf",
                "sha256": "a" * 64,
                "media_type": "application/pdf",
                "expected_text_fragments": ["règlement de consultation"],
                "expected_labels": ["deadline"],
            }
        ],
    }


def test_manifest_parses_closed_document_contract() -> None:
    manifest = parse_manifest(_manifest())

    assert manifest.corpus_id == "corpus-v1"
    assert manifest.documents[0].filename == "rc.pdf"
    assert manifest.documents[0].expected_labels == ("deadline",)


@pytest.mark.parametrize(
    "mutator, code",
    [
        (
            lambda value: value["documents"][0].update({"filename": "../rc.pdf"}),
            "GOLDEN_DOCUMENT_FILENAME_INVALID",
        ),
        (
            lambda value: value["documents"][0].update({"sha256": "invalid"}),
            "GOLDEN_DOCUMENT_HASH_INVALID",
        ),
        (
            lambda value: value["documents"][0].update({"extra": True}),
            "GOLDEN_DOCUMENT_FIELDS_INVALID",
        ),
        (
            lambda value: value["documents"].append(value["documents"][0].copy()),
            "GOLDEN_MANIFEST_DOCUMENT_ID_DUPLICATE",
        ),
    ],
)
def test_manifest_rejects_unsafe_or_ambiguous_documents(mutator, code: str) -> None:
    manifest = _manifest()
    mutator(manifest)

    with pytest.raises(ValueError, match=code):
        parse_manifest(manifest)

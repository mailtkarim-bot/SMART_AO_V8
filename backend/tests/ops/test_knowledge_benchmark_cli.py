from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.modules.knowledge.application.benchmark import (
    BenchmarkManifestError,
    parse_result_payload,
)

FRAGMENT_ID = "33333333-3333-4333-8333-333333333333"


def write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_results_accepts_identifier_only_report(tmp_path: Path) -> None:
    path = write_json(
        tmp_path / "results.json",
        [
            {
                "query_id": "q-01",
                "retrieved_fragment_ids": [FRAGMENT_ID],
                "elapsed_ms": 12.5,
            }
        ],
    )

    results = parse_result_payload(json.loads(path.read_text(encoding="utf-8")))

    assert results[0].query_id == "q-01"
    assert str(results[0].retrieved_fragment_ids[0]) == FRAGMENT_ID
    assert results[0].elapsed_ms == 12.5


@pytest.mark.parametrize("extra_key", ["text", "excerpt", "embedding", "amount"])
def test_load_results_rejects_sensitive_or_unknown_fields(
    tmp_path: Path, extra_key: str
) -> None:
    path = write_json(
        tmp_path / "results.json",
        [
            {
                "query_id": "q-01",
                "retrieved_fragment_ids": [FRAGMENT_ID],
                "elapsed_ms": 12.5,
                extra_key: "must not be accepted",
            }
        ],
    )

    with pytest.raises(BenchmarkManifestError, match="only"):
        parse_result_payload(json.loads(path.read_text(encoding="utf-8")))


def test_load_results_rejects_invalid_fragment_uuid(tmp_path: Path) -> None:
    path = write_json(
        tmp_path / "results.json",
        [
            {
                "query_id": "q-01",
                "retrieved_fragment_ids": ["not-a-uuid"],
                "elapsed_ms": 12.5,
            }
        ],
    )

    with pytest.raises(BenchmarkManifestError, match="UUID"):
        parse_result_payload(json.loads(path.read_text(encoding="utf-8")))

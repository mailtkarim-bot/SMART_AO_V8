"""Validate an identifier-only Golden DCE/RAG manifest and optional run results.

The command never opens or parses DCE documents. An operator supplies a
manifest containing only anonymized identifiers, hashes, classifications and
locators, then optionally a result report containing fragment IDs and timings.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.modules.knowledge.application.benchmark import (
    BenchmarkManifestError,
    QueryBenchmarkResult,
    load_manifest,
    parse_result_payload,
    score_results,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    try:
        manifest = load_manifest(_load_json_object(args.manifest))
        output: dict[str, Any] = {
            "status": "manifest_valid",
            "schema_version": 1,
            "corpus_id": manifest.corpus_id,
            "model_id": manifest.model_id,
            "case_count": len(manifest.cases),
            "fragment_count": sum(len(case.fragment_ids) for case in manifest.cases),
            "query_count": sum(len(case.queries) for case in manifest.cases),
        }
        if args.results is not None:
            summary = score_results(
                manifest=manifest,
                results=_load_results(args.results),
                top_k=args.top_k,
            )
            output.update(
                {
                    "status": "benchmark_valid",
                    "evaluated_query_count": summary.query_count,
                    "recall_at_k": round(summary.recall_at_k, 6),
                    "mean_elapsed_ms": round(summary.mean_elapsed_ms, 3),
                    "p95_elapsed_ms": round(summary.p95_elapsed_ms, 3),
                }
            )
        print(json.dumps(output, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, BenchmarkManifestError) as exc:
        print(
            json.dumps(
                {
                    "status": "invalid_benchmark_input",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                sort_keys=True,
            )
        )
        return 2


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BenchmarkManifestError("manifest must be a JSON object")
    return payload


def _load_results(path: Path) -> list[QueryBenchmarkResult]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_result_payload(payload)


if __name__ == "__main__":
    raise SystemExit(main())

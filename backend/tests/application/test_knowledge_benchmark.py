from __future__ import annotations

from uuid import UUID

import pytest
from app.modules.knowledge.application.benchmark import (
    BenchmarkManifestError,
    QueryBenchmarkResult,
    load_manifest,
    query_sha256,
    score_results,
)

CASE_ID = "11111111-1111-4111-8111-111111111111"
VERSION_ID = "22222222-2222-4222-8222-222222222222"
FRAGMENT_A = "33333333-3333-4333-8333-333333333333"
FRAGMENT_B = "44444444-4444-4444-8444-444444444444"


def manifest_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "corpus_id": "golden-public-v1",
        "model_id": "BAAI/bge-m3",
        "anonymized": True,
        "authorized": True,
        "tenant_scoped": True,
        "cases": [
            {
                "case_id": CASE_ID,
                "dce_version_id": VERSION_ID,
                "fragments": [
                    {
                        "source_fragment_id": FRAGMENT_A,
                        "classification": "PUBLIC",
                        "locator": {"page": 3, "section": "CCTP"},
                    },
                    {
                        "source_fragment_id": FRAGMENT_B,
                        "classification": "INTERNAL_OPERATIONAL",
                        "locator": {"page": 7, "section": "planning"},
                    },
                ],
                "queries": [
                    {
                        "query_id": "q-01",
                        "query_sha256": query_sha256("délais d’exécution"),
                        "expected_fragment_ids": [FRAGMENT_A],
                    },
                    {
                        "query_id": "q-02",
                        "query_sha256": query_sha256("organisation du chantier"),
                        "expected_fragment_ids": [FRAGMENT_B],
                    },
                ],
            }
        ],
    }


def test_load_manifest_accepts_identifier_only_anonymized_payload() -> None:
    manifest = load_manifest(manifest_payload())

    assert manifest.corpus_id == "golden-public-v1"
    assert manifest.model_id == "BAAI/bge-m3"
    assert manifest.cases[0].fragment_ids == {
        UUID(FRAGMENT_A),
        UUID(FRAGMENT_B),
    }


@pytest.mark.parametrize("field", ["text", "excerpt", "embedding", "amount", "storage_key"])
def test_load_manifest_rejects_sensitive_fields(field: str) -> None:
    payload = manifest_payload()
    payload["forbidden"] = {field: "must not be committed"}

    with pytest.raises(BenchmarkManifestError, match="forbidden fields"):
        load_manifest(payload)


def test_load_manifest_rejects_financial_classification() -> None:
    payload = manifest_payload()
    fragments = payload["cases"][0]["fragments"]  # type: ignore[index]
    fragments[0]["classification"] = "FINANCIAL_PRIVATE"  # type: ignore[index]

    with pytest.raises(BenchmarkManifestError, match="classification"):
        load_manifest(payload)


def test_load_manifest_rejects_expected_fragment_from_another_case() -> None:
    payload = manifest_payload()
    queries = payload["cases"][0]["queries"]  # type: ignore[index]
    queries[0]["expected_fragment_ids"] = [VERSION_ID]  # type: ignore[index]

    with pytest.raises(BenchmarkManifestError, match="belong to the case"):
        load_manifest(payload)


def test_score_results_reports_recall_and_latency() -> None:
    manifest = load_manifest(manifest_payload())
    results = [
        QueryBenchmarkResult(
            query_id="q-01",
            retrieved_fragment_ids=(UUID(FRAGMENT_A),),
            elapsed_ms=10.0,
        ),
        QueryBenchmarkResult(
            query_id="q-02",
            retrieved_fragment_ids=(UUID(FRAGMENT_A), UUID(FRAGMENT_B)),
            elapsed_ms=20.0,
        ),
    ]

    summary = score_results(manifest=manifest, results=results, top_k=2)

    assert summary.query_count == 2
    assert summary.recall_at_k == 1.0
    assert summary.mean_elapsed_ms == 15.0
    assert summary.p95_elapsed_ms == 20.0
    assert summary.evaluated_query_ids == ("q-01", "q-02")


def test_score_results_is_bounded_by_top_k() -> None:
    manifest = load_manifest(manifest_payload())
    results = [
        QueryBenchmarkResult(
            query_id="q-02",
            retrieved_fragment_ids=(UUID(FRAGMENT_A), UUID(FRAGMENT_B)),
            elapsed_ms=4.0,
        )
    ]

    summary = score_results(manifest=manifest, results=results, top_k=1)

    assert summary.recall_at_k == 0.0


def test_query_sha256_does_not_return_query_text() -> None:
    digest = query_sha256("texte de requête contrôlé")

    assert len(digest) == 64
    assert "texte" not in digest


def test_load_manifest_rejects_non_anonymized_payload() -> None:
    payload = manifest_payload()
    payload["anonymized"] = False

    with pytest.raises(BenchmarkManifestError, match="anonymized"):
        load_manifest(payload)

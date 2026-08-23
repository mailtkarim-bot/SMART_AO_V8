"""Pure validation and scoring for controlled knowledge benchmarks.

The benchmark contract deliberately carries identifiers and hashes only. It does
not accept document text, embeddings, locators with free-form excerpts, or
financial fields, so an operator can commit a manifest without leaking DCE data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from math import ceil
from statistics import fmean
from typing import Any
from uuid import UUID

from app.modules.knowledge.domain.retrieval import DataClassification

SCHEMA_VERSION = 1
_ALLOWED_CLASSIFICATIONS = frozenset(
    {DataClassification.PUBLIC.value, DataClassification.INTERNAL_OPERATIONAL.value}
)
_CORPUS_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_QUERY_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_FORBIDDEN_KEYS = frozenset(
    {
        "text",
        "excerpt",
        "content",
        "embedding",
        "vector",
        "amount",
        "price",
        "currency",
        "financial",
        "storage_key",
    }
)


class BenchmarkManifestError(ValueError):
    """Raised when a Golden DCE/RAG manifest is unsafe or malformed."""


@dataclass(frozen=True, slots=True)
class BenchmarkQuery:
    query_id: str
    query_sha256: str
    expected_fragment_ids: frozenset[UUID]


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: UUID
    dce_version_id: UUID
    fragment_ids: frozenset[UUID]
    queries: tuple[BenchmarkQuery, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkManifest:
    corpus_id: str
    model_id: str
    cases: tuple[BenchmarkCase, ...]


@dataclass(frozen=True, slots=True)
class QueryBenchmarkResult:
    query_id: str
    retrieved_fragment_ids: tuple[UUID, ...]
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    corpus_id: str
    model_id: str
    query_count: int
    recall_at_k: float
    mean_elapsed_ms: float
    p95_elapsed_ms: float
    evaluated_query_ids: tuple[str, ...]


def load_manifest(payload: Any) -> BenchmarkManifest:
    """Validate and convert a decoded JSON manifest into a safe value object."""

    if not isinstance(payload, dict):
        raise BenchmarkManifestError("manifest must be a JSON object")
    _reject_forbidden_keys(payload)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkManifestError("unsupported schema_version")
    corpus_id = _required_string(payload, "corpus_id")
    if not _CORPUS_ID.fullmatch(corpus_id):
        raise BenchmarkManifestError("corpus_id has an invalid format")
    if payload.get("anonymized") is not True:
        raise BenchmarkManifestError("anonymized must be true")
    if payload.get("authorized") is not True:
        raise BenchmarkManifestError("authorized must be true")
    if payload.get("tenant_scoped") is not True:
        raise BenchmarkManifestError("tenant_scoped must be true")
    model_id = _required_string(payload, "model_id")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise BenchmarkManifestError("cases must be a non-empty array")

    cases: list[BenchmarkCase] = []
    case_ids: set[UUID] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise BenchmarkManifestError("each case must be an object")
        _reject_forbidden_keys(raw_case)
        case_id = _required_uuid(raw_case, "case_id")
        dce_version_id = _required_uuid(raw_case, "dce_version_id")
        if case_id in case_ids:
            raise BenchmarkManifestError("case_id must be unique")
        case_ids.add(case_id)
        raw_fragments = raw_case.get("fragments")
        if not isinstance(raw_fragments, list) or not raw_fragments:
            raise BenchmarkManifestError("fragments must be a non-empty array")
        fragment_ids: set[UUID] = set()
        for raw_fragment in raw_fragments:
            if not isinstance(raw_fragment, dict):
                raise BenchmarkManifestError("each fragment must be an object")
            _reject_forbidden_keys(raw_fragment)
            fragment_id = _required_uuid(raw_fragment, "source_fragment_id")
            if fragment_id in fragment_ids:
                raise BenchmarkManifestError("source_fragment_id must be unique per case")
            fragment_ids.add(fragment_id)
            classification = raw_fragment.get("classification")
            if classification not in _ALLOWED_CLASSIFICATIONS:
                raise BenchmarkManifestError(
                    "fragment classification must be PUBLIC or INTERNAL_OPERATIONAL"
                )
            locator = raw_fragment.get("locator")
            if not isinstance(locator, dict) or not locator:
                raise BenchmarkManifestError("fragment locator must be a non-empty object")
            _reject_forbidden_keys(locator)
        raw_queries = raw_case.get("queries")
        if not isinstance(raw_queries, list) or not raw_queries:
            raise BenchmarkManifestError("queries must be a non-empty array")
        queries: list[BenchmarkQuery] = []
        query_ids: set[str] = set()
        for raw_query in raw_queries:
            if not isinstance(raw_query, dict):
                raise BenchmarkManifestError("each query must be an object")
            _reject_forbidden_keys(raw_query)
            query_id = _required_string(raw_query, "query_id")
            if not _QUERY_ID.fullmatch(query_id) or query_id in query_ids:
                raise BenchmarkManifestError("query_id must be unique and safely formatted")
            query_ids.add(query_id)
            query_sha256 = _required_string(raw_query, "query_sha256")
            if not re.fullmatch(r"[0-9a-f]{64}", query_sha256):
                raise BenchmarkManifestError("query_sha256 must be a lowercase SHA-256")
            raw_expected = raw_query.get("expected_fragment_ids")
            if not isinstance(raw_expected, list) or not raw_expected:
                raise BenchmarkManifestError("expected_fragment_ids must be non-empty")
            expected = frozenset(
                _parse_uuid(value, "expected_fragment_ids") for value in raw_expected
            )
            if not expected.issubset(fragment_ids):
                raise BenchmarkManifestError("expected fragment must belong to the case")
            queries.append(
                BenchmarkQuery(
                    query_id=query_id,
                    query_sha256=query_sha256,
                    expected_fragment_ids=expected,
                )
            )
        cases.append(
            BenchmarkCase(
                case_id=case_id,
                dce_version_id=dce_version_id,
                fragment_ids=frozenset(fragment_ids),
                queries=tuple(queries),
            )
        )
    return BenchmarkManifest(corpus_id=corpus_id, model_id=model_id, cases=tuple(cases))


def score_results(
    *, manifest: BenchmarkManifest, results: list[QueryBenchmarkResult], top_k: int
) -> BenchmarkSummary:
    """Compute recall and latency from an external, identifier-only run report."""

    if not 1 <= top_k <= 50:
        raise BenchmarkManifestError("top_k must be between 1 and 50")
    expected_by_query = {
        query.query_id: query.expected_fragment_ids
        for case in manifest.cases
        for query in case.queries
    }
    if not results:
        raise BenchmarkManifestError("results must be non-empty")
    seen: set[str] = set()
    recalls: list[float] = []
    latencies: list[float] = []
    for result in results:
        if result.query_id in seen or result.query_id not in expected_by_query:
            raise BenchmarkManifestError("results contain an unknown or duplicate query_id")
        seen.add(result.query_id)
        if not result.retrieved_fragment_ids:
            retrieved = set()
        else:
            retrieved = set(result.retrieved_fragment_ids[:top_k])
        if result.elapsed_ms < 0:
            raise BenchmarkManifestError("elapsed_ms must not be negative")
        expected = expected_by_query[result.query_id]
        recalls.append(len(expected & retrieved) / len(expected))
        latencies.append(result.elapsed_ms)
    ordered_latencies = sorted(latencies)
    p95_index = min(len(ordered_latencies) - 1, max(0, ceil(len(ordered_latencies) * 0.95) - 1))
    return BenchmarkSummary(
        corpus_id=manifest.corpus_id,
        model_id=manifest.model_id,
        query_count=len(results),
        recall_at_k=fmean(recalls),
        mean_elapsed_ms=fmean(latencies),
        p95_elapsed_ms=ordered_latencies[p95_index],
        evaluated_query_ids=tuple(sorted(seen)),
    )


def query_sha256(query: str) -> str:
    """Return the only query representation allowed in a committed manifest."""

    if not query.strip():
        raise ValueError("query must not be empty")
    return sha256(query.encode("utf-8")).hexdigest()


def parse_result_payload(payload: Any) -> list[QueryBenchmarkResult]:
    """Parse an identifier-only result report into immutable benchmark values."""

    if not isinstance(payload, list) or not payload:
        raise BenchmarkManifestError("results must be a non-empty JSON array")
    results: list[QueryBenchmarkResult] = []
    for item in payload:
        if not isinstance(item, dict) or set(item) != {
            "query_id",
            "retrieved_fragment_ids",
            "elapsed_ms",
        }:
            raise BenchmarkManifestError(
                "each result must contain only query_id, retrieved_fragment_ids and elapsed_ms"
            )
        query_id = item["query_id"]
        fragment_ids = item["retrieved_fragment_ids"]
        elapsed_ms = item["elapsed_ms"]
        if not isinstance(query_id, str) or not isinstance(fragment_ids, list):
            raise BenchmarkManifestError("result identifiers have invalid types")
        if not isinstance(elapsed_ms, (int, float)) or isinstance(elapsed_ms, bool):
            raise BenchmarkManifestError("elapsed_ms must be numeric")
        parsed_ids: list[UUID] = []
        for value in fragment_ids:
            try:
                parsed_ids.append(UUID(value))
            except (AttributeError, ValueError, TypeError) as exc:
                raise BenchmarkManifestError(
                    "retrieved_fragment_ids must contain UUID strings"
                ) from exc
        results.append(
            QueryBenchmarkResult(
                query_id=query_id,
                retrieved_fragment_ids=tuple(parsed_ids),
                elapsed_ms=float(elapsed_ms),
            )
        )
    return results


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        forbidden = _FORBIDDEN_KEYS.intersection(value)
        if forbidden:
            raise BenchmarkManifestError(
                f"manifest contains forbidden fields: {', '.join(sorted(forbidden))}"
            )
        for child in value.values():
            _reject_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_keys(child)


def _required_string(value: dict[str, Any], key: str) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str) or not candidate.strip():
        raise BenchmarkManifestError(f"{key} must be a non-empty string")
    return candidate


def _required_uuid(value: dict[str, Any], key: str) -> UUID:
    return _parse_uuid(value.get(key), key)


def _parse_uuid(value: Any, key: str) -> UUID:
    if not isinstance(value, str):
        raise BenchmarkManifestError(f"{key} must contain UUID strings")
    try:
        return UUID(value)
    except ValueError as exc:
        raise BenchmarkManifestError(f"{key} contains an invalid UUID") from exc

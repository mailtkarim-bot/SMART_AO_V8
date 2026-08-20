from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class RequestResult:
    url_path: str
    status: int | None
    elapsed_ms: float
    error_code: str | None


def _request(base_url: str, path: str, token: str | None, timeout: float) -> RequestResult:
    started = time.perf_counter()
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    headers = {"Accept": "application/json, application/zip"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, method="GET", headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            response.read(1024)
            error_code = None if 200 <= status < 300 else f"HTTP_{status}"
    except HTTPError as error:
        status = int(error.code)
        error_code = f"HTTP_{status}"
    except (TimeoutError, URLError, OSError, ValueError) as error:
        status = None
        error_code = type(error).__name__
    return RequestResult(
        url_path=path,
        status=status,
        elapsed_ms=(time.perf_counter() - started) * 1000,
        error_code=error_code,
    )


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
    return ordered[index]


def _load_paths(path: Path) -> list[str]:
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError("request file must contain a JSON array of paths")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded SMART_AO VPS load campaign")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--paths-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requests", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1 or args.concurrency > args.requests:
        raise SystemExit("requests must be >= 1 and concurrency must be within requests")
    paths = _load_paths(args.paths_file)
    if not paths:
        raise SystemExit("paths file must not be empty")
    if args.dry_run:
        print(
            json.dumps(
                {
                    "base_url": args.base_url,
                    "paths": paths,
                    "requests": args.requests,
                    "concurrency": args.concurrency,
                    "timeout_seconds": args.timeout_seconds,
                },
                indent=2,
            )
        )
        return 0
    token = os.getenv("SMART_AO_LOAD_BEARER_TOKEN")
    request_paths = [paths[index % len(paths)] for index in range(args.requests)]
    started = datetime.now(tz=UTC)
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        results = list(
            executor.map(
                lambda path: _request(args.base_url, path, token, args.timeout_seconds),
                request_paths,
            )
        )
    durations = [result.elapsed_ms for result in results]
    failures = [result for result in results if result.error_code is not None]
    report = {
        "started_at_utc": started.isoformat(),
        "base_url": args.base_url,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "timeout_seconds": args.timeout_seconds,
        "success_count": len(results) - len(failures),
        "failure_count": len(failures),
        "latency_ms": {
            "min": min(durations),
            "median": statistics.median(durations),
            "p95": _percentile(durations, 0.95),
            "max": max(durations),
        },
        "failures": [asdict(result) for result in failures],
        "paths_count": len(paths),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

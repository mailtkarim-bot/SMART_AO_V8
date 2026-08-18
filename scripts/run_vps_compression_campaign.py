from __future__ import annotations

import argparse
import json
import resource
import statistics
import time
import zipfile
from pathlib import Path

from benchmark_submission_zip_corpus import assemble

PROFILES = (
    ("stored", zipfile.ZIP_STORED, None),
    ("deflated-6", zipfile.ZIP_DEFLATED, 6),
    ("deflated-9", zipfile.ZIP_DEFLATED, 9),
)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated ZIP compression measurements")
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    if args.repetitions < 2:
        raise SystemExit("repetitions must be at least 2")
    files = sorted(args.corpus_dir.glob("*"))
    files = [path for path in files if path.is_file()]
    if not files:
        raise SystemExit("corpus directory must contain at least one file")
    input_bytes = sum(path.stat().st_size for path in files)
    reports = []
    for label, compression, level in PROFILES:
        samples = []
        for repetition in range(args.repetitions * 2):
            warm = repetition >= args.repetitions
            before = resource.getrusage(resource.RUSAGE_SELF)
            started = time.perf_counter()
            archive_bytes, digest, elapsed = assemble(files, compression, level)
            after = resource.getrusage(resource.RUSAGE_SELF)
            samples.append(
                {
                    "warm": warm,
                    "archive_bytes": archive_bytes,
                    "archive_sha256": digest,
                    "elapsed_seconds": elapsed,
                    "wall_seconds": time.perf_counter() - started,
                    "user_cpu_seconds_delta": after.ru_utime - before.ru_utime,
                    "system_cpu_seconds_delta": after.ru_stime - before.ru_stime,
                }
            )
        cold = [sample for sample in samples if not sample["warm"]]
        warm = [sample for sample in samples if sample["warm"]]
        elapsed = [float(sample["elapsed_seconds"]) for sample in samples]
        reports.append(
            {
                "profile": label,
                "compression": compression,
                "compresslevel": level,
                "input_bytes": input_bytes,
                "archive_bytes": samples[-1]["archive_bytes"],
                "reduction_percent": round(
                    (1 - samples[-1]["archive_bytes"] / input_bytes) * 100, 4
                ),
                "hashes_identical": len({sample["archive_sha256"] for sample in samples}) == 1,
                "cold_elapsed_median_seconds": statistics.median(
                    sample["elapsed_seconds"] for sample in cold
                ),
                "warm_elapsed_median_seconds": statistics.median(
                    sample["elapsed_seconds"] for sample in warm
                ),
                "elapsed_p95_seconds": _percentile(elapsed, 0.95),
                "samples": samples,
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "corpus_dir": str(args.corpus_dir),
                "repetitions_per_temperature": args.repetitions,
                "profiles": reports,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

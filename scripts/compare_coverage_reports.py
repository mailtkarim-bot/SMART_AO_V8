from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _missing(file_data: dict[str, object]) -> set[int]:
    return set(file_data.get("missing_lines", []))


def _branch_set(file_data: dict[str, object], key: str) -> set[str]:
    branches = file_data.get(key, [])
    return {json.dumps(branch, sort_keys=True) for branch in branches}


def _partial(file_data: dict[str, object]) -> set[str]:
    return _branch_set(file_data, "executed_branches") - _branch_set(
        file_data, "missing_branches"
    )


def compare(local_path: Path, ci_path: Path) -> dict[str, object]:
    local = _load(local_path)
    ci = _load(ci_path)
    local_files = local["files"]
    ci_files = ci["files"]
    assert isinstance(local_files, dict)
    assert isinstance(ci_files, dict)
    file_diffs = []
    for filename in sorted(set(local_files) | set(ci_files)):
        local_file = local_files.get(filename, {})
        ci_file = ci_files.get(filename, {})
        assert isinstance(local_file, dict)
        assert isinstance(ci_file, dict)
        local_summary = local_file.get("summary", {})
        ci_summary = ci_file.get("summary", {})
        assert isinstance(local_summary, dict)
        assert isinstance(ci_summary, dict)
        line_delta = float(ci_summary.get("percent_covered", 0)) - float(
            local_summary.get("percent_covered", 0)
        )
        branch_delta = float(ci_summary.get("percent_covered_branches", 0)) - float(
            local_summary.get("percent_covered_branches", 0)
        )
        missing_local = _missing(local_file)
        missing_ci = _missing(ci_file)
        partial_local = _partial(local_file)
        partial_ci = _partial(ci_file)
        if line_delta or branch_delta or missing_local != missing_ci:
            file_diffs.append(
                {
                    "file": filename,
                    "line_delta_ci_minus_local": round(line_delta, 4),
                    "branch_delta_ci_minus_local": round(branch_delta, 4),
                    "local_missing_lines": sorted(missing_local),
                    "ci_missing_lines": sorted(missing_ci),
                    "local_partial_branches": sorted(partial_local),
                    "ci_partial_branches": sorted(partial_ci),
                }
            )
    return {
        "local_totals": local["totals"],
        "ci_totals": ci["totals"],
        "percent_delta_ci_minus_local": round(
            float(ci["totals"]["percent_covered"])
            - float(local["totals"]["percent_covered"]),
            4,
        ),
        "files_with_differences": file_diffs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare coverage JSON reports")
    parser.add_argument("--local", type=Path, required=True)
    parser.add_argument("--ci", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.local, args.ci)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

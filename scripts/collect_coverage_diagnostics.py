from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def _run_version(command: list[str]) -> str:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    return (result.stdout or result.stderr).strip()


def _git_value(root: Path, *args: str) -> str:
    return _run_version(["git", "-C", str(root), *args])


def collect_environment(root: Path) -> dict[str, object]:
    return {
        "collected_at_utc": datetime.now(tz=UTC).isoformat(),
        "python": sys.version,
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "pytest": _run_version([sys.executable, "-m", "pytest", "--version"]),
        "coverage": _run_version([sys.executable, "-m", "coverage", "--version"]),
        "uv": _run_version(["uv", "--version"]),
        "git_commit": _git_value(root, "rev-parse", "HEAD"),
        "git_status_porcelain": _git_value(root, "status", "--porcelain"),
        "lockfile_sha256": _sha256(root / "uv.lock"),
    }


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect local coverage diagnostics")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--environment-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    environment_path = output_dir / "environment.json"
    environment_path.write_text(
        json.dumps(collect_environment(root), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.environment_only:
        return 0
    command = [
        sys.executable,
        "-m",
        "pytest",
        "backend/tests",
        "-q",
        "--cov=app",
        "--cov-report=term-missing",
        f"--cov-report=json:{output_dir / 'coverage.json'}",
        f"--cov-report=xml:{output_dir / 'coverage.xml'}",
        "--cov-fail-under=0",
    ]
    result = subprocess.run(command, cwd=root, check=False)
    (output_dir / "pytest-exit-code.txt").write_text(
        f"{result.returncode}\n", encoding="utf-8"
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

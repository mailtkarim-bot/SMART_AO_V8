from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPOSITORY_ROOT / "scripts" / "start_local_postgres.sh"


FAKE_DOCKER = """\
#!/usr/bin/env bash
set -Eeuo pipefail
case "${1:-}" in
  container)
    exit 1
    ;;
  volume)
    if [[ "${2:-}" == "inspect" ]]; then exit 1; fi
    if [[ "${2:-}" == "create" ]]; then printf 'test-volume\\n'; exit 0; fi
    ;;
  run)
    printf 'test-container-id\\n'
    ;;
  inspect)
    printf 'healthy\\n'
    ;;
  *)
    exit 0
    ;;
esac
"""


def _run_script(tmp_path: Path, *args: str, **overrides: str) -> subprocess.CompletedProcess[str]:
    docker_dir = tmp_path / "bin"
    docker_dir.mkdir()
    docker = docker_dir / "docker"
    docker.write_text(FAKE_DOCKER, encoding="utf-8")
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{docker_dir}:{environment['PATH']}"
    environment.update(overrides)
    return subprocess.run(
        [str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_help_is_available_without_docker() -> None:
    result = subprocess.run(
        [str(SCRIPT), "--help"],
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
    )

    assert result.returncode == 0
    assert "SMART_AO_TEST_DATABASE_URL" in result.stdout
    assert "SMART_AO_TEST_DB_PASSWORD" in result.stdout


def test_invalid_port_is_rejected_before_container_creation(tmp_path: Path) -> None:
    result = _run_script(tmp_path, SMART_AO_TEST_DB_PORT="invalid")

    assert result.returncode == 1
    assert "must be numeric" in result.stderr


def test_fake_docker_start_does_not_print_password(tmp_path: Path) -> None:
    result = _run_script(
        tmp_path,
        SMART_AO_TEST_DB_PORT="55433",
        SMART_AO_TEST_DB_PASSWORD="super-secret-local",  # pragma: allowlist secret
        SMART_AO_POSTGRES_WAIT_SECONDS="2",
    )

    assert result.returncode == 0
    assert "healthy on 127.0.0.1:55433" in result.stdout
    assert "super-secret-local" not in result.stdout
    assert "super-secret-local" not in result.stderr

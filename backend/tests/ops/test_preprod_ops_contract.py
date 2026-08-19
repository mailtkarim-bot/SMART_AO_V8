from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OPS = ROOT / "ops"


def test_preprod_operations_scripts_are_executable_and_syntactically_valid() -> None:
    scripts = sorted(OPS.glob("*.sh"))
    assert scripts
    for script in scripts:
        assert script.stat().st_mode & 0o111, script
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_compose_runtime_images_are_digest_pinned_and_clamav_is_private() -> None:
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")
    image_lines = [
        line.strip()
        for line in compose.splitlines()
        if line.strip().startswith("image:")
    ]
    assert image_lines
    assert all("@sha256:" in line for line in image_lines)
    assert "3310:" not in compose
    assert "3310" in compose


def test_7b_units_and_rotation_contract_are_present() -> None:
    expected = {
        "smart-ao-backup.service",
        "smart-ao-backup.timer",
        "smart-ao-healthcheck.service",
        "smart-ao-healthcheck.timer",
        "smart-ao-health-alert.service",
    }
    assert {path.name for path in (OPS / "systemd").iterdir()} >= expected
    runbook = (OPS / "README.md").read_text(encoding="utf-8")
    for marker in ("restore-preprod.sh", "rotate-jwt-key-preprod.sh", "SHA-256", "json-file"):
        assert marker in runbook


def test_deploy_starts_submission_webhook_worker_explicitly() -> None:
    deploy_script = (OPS / "deploy-preprod.sh").read_text(encoding="utf-8")
    assert "submission-export-webhook-worker" in deploy_script
    assert (
        "compose up -d backend dce-retention-worker submission-export-webhook-worker"
        in deploy_script
    )

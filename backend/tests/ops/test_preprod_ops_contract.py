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


def test_deploy_starts_submission_notification_workers_explicitly() -> None:
    deploy_script = (OPS / "deploy-preprod.sh").read_text(encoding="utf-8")
    assert "submission-export-webhook-worker" in deploy_script
    assert "submission-export-smtp-worker" in deploy_script
    assert (
        "compose up -d backend dce-retention-worker submission-export-webhook-worker "
        "submission-export-smtp-worker"
        in deploy_script
    )


def test_caddy_routes_all_health_endpoints_to_backend() -> None:
    caddyfile = (OPS / "Caddyfile").read_text(encoding="utf-8")
    assert "request_body {\n        max_size 150MB\n    }" in caddyfile
    assert "Content-Security-Policy" in caddyfile
    assert "@health path /healthz /healthz/*" in caddyfile
    health_block = caddyfile.split("@health path", maxsplit=1)[1].split("handle {", maxsplit=1)[0]
    assert "reverse_proxy backend:8000" in health_block
    assert 'respond "ok" 200' not in health_block


def test_preprod_trusts_forwarded_client_ip_only_on_internal_proxy_network() -> None:
    dockerfile = (OPS / "docker/backend.Dockerfile").read_text(encoding="utf-8")
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")
    assert "--proxy-headers" in dockerfile
    assert "--forwarded-allow-ips=172.30.0.0/24" in dockerfile
    assert "subnet: 172.30.0.0/24" in compose
    assert "  migrate:\n" in compose
    assert 'command: ["alembic", "-c", "/app/backend/alembic.ini", "upgrade", "head"]' in compose
    assert compose.count("service_completed_successfully") >= 7
    assert 'backend:\n' in compose and '      - internal\n' in compose


def test_preprod_services_use_minimal_environment_allowlists() -> None:
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")
    assert "env_file:" not in compose

    backend = compose.split("  backend:", maxsplit=1)[1].split(
        "  dce-retention-worker:", maxsplit=1
    )[0]
    retention = compose.split("  dce-retention-worker:", maxsplit=1)[1].split(
        "  submission-export-webhook-worker:", maxsplit=1
    )[0]
    webhook = compose.split("  submission-export-webhook-worker:", maxsplit=1)[1].split(
        "  submission-export-smtp-worker:", maxsplit=1
    )[0]
    smtp = compose.split("  submission-export-smtp-worker:", maxsplit=1)[1].split(
        "\n  postgres:", maxsplit=1
    )[0]

    assert "SMART_AO_JWT_SIGNING_KEY" in backend
    assert "SMART_AO_JWT_KEY_ID" in backend
    assert "SMART_AO_JWT_VERIFICATION_KEYS_JSON" in backend
    assert "SMART_AO_JWT_SIGNING_KEY" not in retention
    assert "SMART_AO_JWT_SIGNING_KEY" not in webhook
    assert "SMART_AO_JWT_SIGNING_KEY" not in smtp
    assert "SMART_AO_EXPORT_WEBHOOK_SECRET" in webhook
    assert "POSTGRES_PASSWORD" not in backend
    assert "POSTGRES_PASSWORD" not in retention
    assert "POSTGRES_PASSWORD" not in webhook
    assert "POSTGRES_PASSWORD" not in smtp


def test_deploy_validates_libpq_password_alignment() -> None:
    deploy_script = (OPS / "deploy-preprod.sh").read_text(encoding="utf-8")
    assert "PGPASSWORD" in deploy_script
    assert 'PGPASSWORD}" == "${POSTGRES_PASSWORD}' in deploy_script


def test_readiness_contract_uses_shared_schema_head() -> None:
    application = (ROOT / "backend/app/bootstrap/application.py").read_text(encoding="utf-8")
    schema = (ROOT / "backend/app/platform/persistence/schema.py").read_text(encoding="utf-8")
    assert "from app.platform.persistence.schema import EXPECTED_ALEMBIC_HEAD" in application
    assert "EXPECTED_ALEMBIC_HEAD" in application
    assert 'EXPECTED_ALEMBIC_HEAD = "20260825_0062"' in schema


def test_healthcheck_validates_application_json_payloads() -> None:
    healthcheck = (OPS / "healthcheck-preprod.sh").read_text(encoding="utf-8")
    assert 'live_body="$(curl' in healthcheck
    assert 'ready_body="$(curl' in healthcheck
    assert '"process"[[:space:]]*:[[:space:]]*"ok"' in healthcheck
    assert '"database"[[:space:]]*:[[:space:]]*"ok"' in healthcheck
    assert '"schema"[[:space:]]*:[[:space:]]*"ok"' in healthcheck
    assert '"clamav"[[:space:]]*:[[:space:]]*"ok"' in healthcheck


def test_backend_docker_context_excludes_demonstrations_and_tests() -> None:
    dockerignore = (ROOT / "ops/docker/backend.Dockerfile.dockerignore").read_text(
        encoding="utf-8"
    )
    assert "backend/app/demonstrations/" in dockerignore
    assert "backend/tests/" in dockerignore
    assert "web/" in dockerignore
    # The frontend image must keep its own context: the shared root ignore
    # must not exclude web/, or frontend.Dockerfile can never build.
    root_ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert not root_ignore.startswith("web/")
    assert "\nweb/\n" not in root_ignore
    frontend_ignore = (ROOT / "ops/docker/frontend.Dockerfile.dockerignore").read_text(
        encoding="utf-8"
    )
    assert "backend/" in frontend_ignore


def test_dev_compose_is_loopback_bound_and_not_repurposable_as_preprod() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert 'SMART_AO_ENV: development' in compose
    assert '"127.0.0.1:${SMART_AO_POSTGRES_HOST_PORT:-5432}:5432"' in compose
    assert '"127.0.0.1:8000:8000"' in compose
    assert "local-development-signing-key-change-me" in compose
    assert "dev-only-signing-key" not in compose
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "SMART_AO_ENV=development" in env_example
    assert "SMART_AO_JWT_SIGNING_KEY=" in env_example
    assert "local-development-signing-key-change-me-" in env_example
    assert 'command: ["alembic", "-c", "/app/backend/alembic.ini", "upgrade", "head"]' in compose
    assert compose.count("no-new-privileges:true") >= 5
    assert "service_completed_successfully" in compose
    local_override = (ROOT / "compose.local-dev.yml").read_text(encoding="utf-8")
    assert '"127.0.0.1:5433:5432"' in local_override


def test_frontend_image_and_service_run_non_root_with_healthcheck() -> None:
    dockerfile = (OPS / "docker/frontend.Dockerfile").read_text(encoding="utf-8")
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")
    caddyfile = (OPS / "Caddyfile").read_text(encoding="utf-8")
    assert "USER nginx" in dockerfile
    assert "EXPOSE 8080" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    frontend = compose.split("  frontend:\n    build:", maxsplit=1)[1].split(
        "  backend:", maxsplit=1
    )[0]
    assert '      - "8080"' in frontend
    assert "healthcheck:" in frontend
    assert "reverse_proxy frontend:8080" in caddyfile


def test_ci_audits_frontend_production_dependencies() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "name: Frontend dependency audit" in workflow
    assert "pnpm audit --prod --audit-level high" in workflow


def test_egress_services_join_private_and_edge_networks() -> None:
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")
    clamav = compose.split("  clamav:", maxsplit=1)[1].split(
        "\n\n  volumes:", maxsplit=1
    )[0]
    webhook = compose.split("  submission-export-webhook-worker:", maxsplit=1)[1].split(
        "\n  postgres:", maxsplit=1
    )[0]
    for service in (clamav, webhook):
        assert "      - internal" in service
        assert "      - edge" in service


def test_optional_dependency_build_flags_are_explicit() -> None:
    dockerfile = (OPS / "docker/backend.Dockerfile").read_text(encoding="utf-8")
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")
    assert "ARG SMART_AO_INSTALL_CONNECTORS=0" in dockerfile
    assert "ARG SMART_AO_INSTALL_OBJECT_STORAGE=0" in dockerfile
    assert "uv sync --frozen --no-dev --no-editable --extra object-storage" in dockerfile
    assert "uv sync --frozen --no-dev --no-editable --extra connectors" in dockerfile
    assert "SMART_AO_INSTALL_CONNECTORS" in compose
    assert "SMART_AO_INSTALL_RAG" in compose
    assert "SMART_AO_INSTALL_DOCUMENT_ADVANCED" in compose
    assert "SMART_AO_INSTALL_OBJECT_STORAGE" in compose


def test_insee_connector_is_disabled_by_default_and_secret_is_backend_only() -> None:
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")
    backend = compose.split("  backend:", maxsplit=1)[1].split(
        "  dce-retention-worker:", maxsplit=1
    )[0]
    retention = compose.split("  dce-retention-worker:", maxsplit=1)[1].split(
        "  submission-export-webhook-worker:", maxsplit=1
    )[0]
    webhook = compose.split("  submission-export-webhook-worker:", maxsplit=1)[1].split(
        "  submission-export-smtp-worker:", maxsplit=1
    )[0]
    smtp = compose.split("  submission-export-smtp-worker:", maxsplit=1)[1].split(
        "\n  postgres:", maxsplit=1
    )[0]
    assert "SMART_AO_INSEE_ENABLED: ${SMART_AO_INSEE_ENABLED:-0}" in backend
    assert "SMART_AO_INSEE_API_TOKEN: ${SMART_AO_INSEE_API_TOKEN:-}" in backend
    assert "SMART_AO_INSEE_API_TOKEN" not in retention
    assert "SMART_AO_INSEE_API_TOKEN" not in webhook
    assert "SMART_AO_INSEE_API_TOKEN" not in smtp


def test_optional_notifications_build_and_runtime_flags_are_explicit() -> None:
    dockerfile = (OPS / "docker/backend.Dockerfile").read_text(encoding="utf-8")
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")
    assert "ARG SMART_AO_INSTALL_NOTIFICATIONS=0" in dockerfile
    assert "uv sync --frozen --no-dev --no-editable --extra notifications" in dockerfile
    assert "SMART_AO_INSTALL_NOTIFICATIONS" in compose
    assert "SMART_AO_SMTP_ENABLED: ${SMART_AO_SMTP_ENABLED:-0}" in compose
    assert "SMART_AO_SMTP_TO: ${SMART_AO_SMTP_TO:-}" in compose
    assert "python -m app.workers.submission_export_smtp" in compose


def test_smtp_credentials_are_allowlisted_only_for_backend() -> None:
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")
    backend = compose.split("  backend:", maxsplit=1)[1].split(
        "  dce-retention-worker:", maxsplit=1
    )[0]
    retention = compose.split("  dce-retention-worker:", maxsplit=1)[1].split(
        "  submission-export-webhook-worker:", maxsplit=1
    )[0]
    webhook = compose.split("  submission-export-webhook-worker:", maxsplit=1)[1].split(
        "  submission-export-smtp-worker:", maxsplit=1
    )[0]
    smtp = compose.split("  submission-export-smtp-worker:", maxsplit=1)[1].split(
        "\n  postgres:", maxsplit=1
    )[0]
    assert "SMART_AO_SMTP_PASSWORD" in backend
    assert "SMART_AO_SMTP_USERNAME" in backend
    assert "SMART_AO_SMTP_PASSWORD" not in retention
    assert "SMART_AO_SMTP_PASSWORD" not in webhook
    assert "SMART_AO_SMTP_PASSWORD" in smtp
    assert "SMART_AO_SMTP_TO" in smtp


def test_validation_commands_install_calendar_extra() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "uv sync --group dev --extra calendar" in makefile
    assert "uv run --extra calendar pytest" in makefile


def test_optional_calendar_build_flag_is_explicit() -> None:
    dockerfile = (OPS / "docker/backend.Dockerfile").read_text(encoding="utf-8")
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")
    assert "ARG SMART_AO_INSTALL_CALENDAR=0" in dockerfile
    assert "uv sync --frozen --no-dev --no-editable --extra calendar" in dockerfile
    assert "SMART_AO_INSTALL_CALENDAR" in compose
    assert "SMART_AO_CALENDAR_ENABLED: ${SMART_AO_CALENDAR_ENABLED:-0}" in compose


def test_boamp_public_search_is_explicit_and_secretless() -> None:
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")
    backend = compose.split("  backend:", maxsplit=1)[1].split(
        "  dce-retention-worker:", maxsplit=1
    )[0]
    assert "SMART_AO_BOAMP_ENABLED: ${SMART_AO_BOAMP_ENABLED:-0}" in backend
    assert "SMART_AO_BOAMP_BASE_URL" in backend
    assert "SMART_AO_BOAMP_TIMEOUT_SECONDS" in backend
    assert "BOAMP_API_TOKEN" not in compose


def test_dce_extraction_wrapper_is_one_shot_and_uses_private_env() -> None:
    wrapper = (OPS / "run-dce-extraction-preprod.sh").read_text(encoding="utf-8")
    assert '[[ $# -ne 2 ]]' in wrapper
    assert 'stat -c \'%a\' "$ENV_FILE"' in wrapper
    assert '"$ENV_FILE"' in wrapper
    assert "run --rm --no-deps --no-ansi backend" in wrapper
    assert "python -m app.workers.dce_extraction" in wrapper
    assert "--tenant-id \"$tenant_id\"" in wrapper
    assert "--dce-document-id \"$dce_document_id\"" in wrapper


def test_dce_analysis_wrapper_is_one_shot_and_uses_private_env() -> None:
    wrapper = (OPS / "run-dce-analysis-preprod.sh").read_text(encoding="utf-8")
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")

    assert '[[ $# -ne 2 ]]' in wrapper
    assert 'stat -c \'%a\' "$ENV_FILE"' in wrapper
    assert '"$ENV_FILE"' in wrapper
    assert "--profile dce-analysis run --rm --no-deps --no-ansi dce-rc-analysis-runner" in wrapper
    assert "python -m app.workers.dce_analysis" in wrapper
    assert "--tenant-id \"$tenant_id\"" in wrapper
    assert "--dce-version-id \"$dce_version_id\"" in wrapper
    assert "dce-rc-analysis-runner:" in compose
    assert 'profiles: ["dce-analysis"]' in compose
    assert 'command: ["python", "-m", "app.workers.dce_analysis"]' in compose
    assert "restart: \"no\"" in compose
    assert "dce-rc-analysis-runner" not in compose.split("  backend:", maxsplit=1)[1].split(
        "  dce-retention-worker:", maxsplit=1
    )[0]


def test_dce_requirements_wrapper_is_one_shot_and_profiled() -> None:
    wrapper = (OPS / "run-dce-requirements-preprod.sh").read_text(encoding="utf-8")
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")

    assert '[[ $# -ne 3 ]]' in wrapper
    assert 'stat -c \'%a\' "$ENV_FILE"' in wrapper
    assert (
        "--profile dce-requirements run --rm --no-deps --no-ansi "
        "dce-requirements-runner"
    ) in wrapper
    assert "python -m app.workers.dce_requirements" in wrapper
    assert "--tenant-id \"$tenant_id\"" in wrapper
    assert "--dce-version-id \"$dce_version_id\"" in wrapper
    assert "--dce-rc-analysis-id \"$dce_rc_analysis_id\"" in wrapper
    assert "dce-requirements-runner:" in compose
    assert 'profiles: ["dce-requirements"]' in compose
    assert 'command: ["python", "-m", "app.workers.dce_requirements"]' in compose
    assert "restart: \"no\"" in compose


def test_rag_indexing_is_explicitly_opt_in_and_one_shot() -> None:
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")
    worker = (OPS / "run-knowledge-embeddings-preprod.sh").read_text(encoding="utf-8")

    assert "SMART_AO_RAG_ENABLED: ${SMART_AO_RAG_ENABLED:-0}" in compose
    assert "SMART_AO_RAG_INDEXING_ENABLED: ${SMART_AO_RAG_INDEXING_ENABLED:-0}" in compose
    assert "SMART_AO_BGE_LOCAL_FILES_ONLY: ${SMART_AO_BGE_LOCAL_FILES_ONLY:-1}" in compose
    assert "python -m app.workers.knowledge_embeddings" in worker
    assert "--tenant-id \"$tenant_id\"" in worker
    assert "--case-id \"$case_id\"" in worker
    assert "--dce-version-id \"$dce_version_id\"" in worker
    assert '[[ $# -ne 3 ]]' in worker
    assert 'stat -c \'%a\' "$ENV_FILE"' in worker
    assert "run --rm --no-deps --no-ansi backend" in worker
    assert "ports:" not in worker


def test_rag_runtime_does_not_receive_unrelated_credentials() -> None:
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")
    backend = compose.split("  backend:", maxsplit=1)[1].split(
        "  dce-retention-worker:", maxsplit=1
    )[0]

    assert "SMART_AO_RAG_ENABLED" in backend
    assert "SMART_AO_RAG_INDEXING_ENABLED" in backend
    assert "SMART_AO_JWT_SIGNING_KEY" in backend
    assert "SMART_AO_SMTP_PASSWORD" in backend
    assert "SMART_AO_INSEE_API_TOKEN" in backend
    assert "SMART_AO_EXPORT_WEBHOOK_SECRET" not in backend


def test_signature_http_configuration_is_backend_only_and_fail_closed() -> None:
    compose = (OPS / "docker-compose.preprod.yml").read_text(encoding="utf-8")
    backend = compose.split("  backend:", maxsplit=1)[1].split(
        "  dce-retention-worker:", maxsplit=1
    )[0]
    retention = compose.split("  dce-retention-worker:", maxsplit=1)[1].split(
        "  submission-export-webhook-worker:", maxsplit=1
    )[0]
    webhook = compose.split("  submission-export-webhook-worker:", maxsplit=1)[1].split(
        "  submission-export-smtp-worker:", maxsplit=1
    )[0]
    smtp = compose.split("  submission-export-smtp-worker:", maxsplit=1)[1].split(
        "\n  postgres:", maxsplit=1
    )[0]

    assert "SMART_AO_SIGNATURE_PROVIDER: ${SMART_AO_SIGNATURE_PROVIDER:-}" in backend
    assert "SMART_AO_SIGNATURE_CALLBACK_SECRET: ${SMART_AO_SIGNATURE_CALLBACK_SECRET:-}" in backend
    for unrelated_service in (retention, webhook, smtp):
        assert "SMART_AO_SIGNATURE_CALLBACK_SECRET" not in unrelated_service
        assert "SMART_AO_SIGNATURE_PROVIDER" not in unrelated_service

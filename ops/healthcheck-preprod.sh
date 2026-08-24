#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OPS_DIR="${ROOT_DIR}/ops"
ENV_FILE="${OPS_DIR}/.env.preprod"
COMPOSE_FILE="${OPS_DIR}/docker-compose.preprod.yml"
BACKUP_DIR="${SMART_AO_BACKUP_DIR:-/var/backups/smart-ao}"
MAX_BACKUP_AGE_HOURS="${SMART_AO_MAX_BACKUP_AGE_HOURS:-26}"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

load_environment() {
  [[ -f "${ENV_FILE}" ]] || fail "missing ${ENV_FILE}"
  [[ "$(stat -c '%a' "${ENV_FILE}")" == "600" ]] || fail "${ENV_FILE} must have mode 600"
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
}

compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

main() {
  command -v docker >/dev/null 2>&1 || fail "docker is required"
  command -v curl >/dev/null 2>&1 || fail "curl is required"
  load_environment
  [[ "${SMART_AO_PUBLIC_HOST:-}" != "" ]] || fail "SMART_AO_PUBLIC_HOST is required"
  [[ "${MAX_BACKUP_AGE_HOURS}" =~ ^[0-9]+$ ]] || fail "SMART_AO_MAX_BACKUP_AGE_HOURS must be an integer"

  local live_body ready_body
  live_body="$(curl --fail --silent --show-error --max-time 10 \
    --resolve "${SMART_AO_PUBLIC_HOST}:443:127.0.0.1" \
    "https://${SMART_AO_PUBLIC_HOST}/healthz/live")"
  grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' <<<"${live_body}" \
    || fail "application liveness payload is not healthy"
  grep -Eq '"process"[[:space:]]*:[[:space:]]*"ok"' <<<"${live_body}" \
    || fail "application liveness process check is not healthy"

  ready_body="$(curl --fail --silent --show-error --max-time 10 \
    --resolve "${SMART_AO_PUBLIC_HOST}:443:127.0.0.1" \
    "https://${SMART_AO_PUBLIC_HOST}/healthz/ready")"
  grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' <<<"${ready_body}" \
    || fail "application readiness payload is not healthy"
  grep -Eq '"database"[[:space:]]*:[[:space:]]*"ok"' <<<"${ready_body}" \
    || fail "application database readiness check is not healthy"
  grep -Eq '"schema"[[:space:]]*:[[:space:]]*"ok"' <<<"${ready_body}" \
    || fail "application schema readiness check is not healthy"
  grep -Eq '"clamav"[[:space:]]*:[[:space:]]*"ok"' <<<"${ready_body}" \
    || fail "application ClamAV readiness check is not healthy"

  local services
  services="$(compose ps --format '{{.Service}} {{.Health}}')"
  grep -Eq '^postgres (healthy|running)$' <<<"${services}" || fail "PostgreSQL is not healthy"
  grep -Eq '^clamav (healthy|running)$' <<<"${services}" || fail "ClamAV is not healthy"
  grep -Eq '^backend (healthy|running)$' <<<"${services}" || fail "backend is not healthy"
  grep -Eq '^caddy (healthy|running)$' <<<"${services}" || fail "Caddy is not running"

  if compose config | grep -Eq '(^|[^0-9])3310:[0-9]'; then
    fail "ClamAV port 3310 must never be published"
  fi

  if [[ "${SMART_AO_BACKUP_REQUIRE_FRESH:-1}" == "1" ]]; then
    local max_age_minutes=$((MAX_BACKUP_AGE_HOURS * 60))
    find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'smart_ao_*.sql.gz' -mmin "-${max_age_minutes}" -print -quit \
      | grep -q . || fail "no fresh PostgreSQL backup found in ${BACKUP_DIR}"
  fi
  printf 'Preproduction healthcheck passed at %s\n' "$(date -u +%FT%TZ)"
}

main "$@"

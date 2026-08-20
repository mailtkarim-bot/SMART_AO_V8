#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OPS_DIR="${ROOT_DIR}/ops"
ENV_FILE="${OPS_DIR}/.env.preprod"
COMPOSE_FILE="${OPS_DIR}/docker-compose.preprod.yml"

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
  for variable in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD; do
    [[ -n "${!variable:-}" ]] || fail "${variable} is required"
    [[ "${!variable}" != REPLACE_WITH_* ]] || fail "${variable} still contains a placeholder"
  done
}

compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

usage() {
  cat <<'EOF'
Usage: ops/restore-preprod.sh <backup.sql.gz> [verify]

The default mode restores into a temporary isolated PostgreSQL database,
checks required tables and drops the temporary database. It never overwrites
SMART_AO_DATABASE_URL or POSTGRES_DB.
EOF
}

main() {
  [[ "${1:-}" != "" && "${1:-}" != "-h" ]] || { usage; exit 2; }
  command -v docker >/dev/null 2>&1 || fail "docker is required"
  command -v gzip >/dev/null 2>&1 || fail "gzip is required"
  command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is required"
  local backup_file="$1"
  [[ -f "${backup_file}" ]] || fail "backup does not exist: ${backup_file}"
  load_environment

  local manifest="${backup_file%.sql.gz}.sha256"
  if [[ -f "${manifest}" ]]; then
    (cd "$(dirname -- "${manifest}")" && sha256sum -c "$(basename -- "${manifest}")" --ignore-missing)
  else
    printf 'WARNING: no checksum manifest found beside %s\n' "${backup_file}" >&2
  fi

  local restore_db="smart_ao_restore_$(date -u +%Y%m%d%H%M%S)_$RANDOM"
  [[ "${restore_db}" != "${POSTGRES_DB}" ]] || fail "isolated restore database collides with primary database"
  local cleanup_done=0
  cleanup() {
    if [[ "${cleanup_done}" == 0 ]]; then
      compose exec -T postgres dropdb --if-exists -U "${POSTGRES_USER}" "${restore_db}" >/dev/null 2>&1 || true
    fi
  }
  trap cleanup EXIT

  compose exec -T postgres createdb -U "${POSTGRES_USER}" "${restore_db}"
  gzip -dc -- "${backup_file}" | compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d "${restore_db}" >/dev/null
  local table_count
  table_count="$(compose exec -T postgres psql -U "${POSTGRES_USER}" -d "${restore_db}" -tAc "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public'")"
  [[ "${table_count}" =~ ^[[:space:]]*[1-9][0-9]*[[:space:]]*$ ]] || fail "restored database has no public tables"
  compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d "${restore_db}" \
    -tAc "SELECT to_regclass('public.tenants'), to_regclass('public.command_receipts'), to_regclass('public.outbox_messages')" \
    | grep -q 'tenants.*command_receipts.*outbox_messages' \
    || fail "restored database is missing required durability tables"
  cleanup_done=1
  compose exec -T postgres dropdb --if-exists -U "${POSTGRES_USER}" "${restore_db}" >/dev/null
  printf 'Isolated restore verification passed for %s\n' "${backup_file}"
}

main "$@"

#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OPS_DIR="${ROOT_DIR}/ops"
ENV_FILE="${OPS_DIR}/.env.preprod"
COMPOSE_FILE="${OPS_DIR}/docker-compose.preprod.yml"
BACKUP_DIR="${SMART_AO_BACKUP_DIR:-/var/backups/smart-ao}"
LOCK_FILE="${SMART_AO_DEPLOY_LOCK:-/var/lock/smart-ao-preprod-deploy.lock}"

usage() {
  cat <<'EOF'
Usage: ops/deploy-preprod.sh <config|deploy|smoke|status|backup|restore|healthcheck|rotate-key>

Commands:
  config  validate the env file and resolved Compose configuration
  deploy  validate, backup PostgreSQL, pull/build pinned images, migrate and start services
  smoke   verify public live/readiness endpoints and private service health
  status  show the Compose service state
  backup  create PostgreSQL, private volume and checksum backups
  restore verify one backup in an isolated temporary PostgreSQL database
  healthcheck run HTTPS, dependency, port exposure and backup freshness checks
  rotate-key rotate the JWT key only after explicit operator confirmation

The script never performs an automatic database downgrade. A failed release leaves
its backup and logs available for an explicit, reviewed rollback procedure.
EOF
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command is missing: $1"
}

load_environment() {
  [[ -f "${ENV_FILE}" ]] || fail "missing ${ENV_FILE}; copy .env.preprod.example and fill it locally"
  [[ "$(stat -c '%a' "${ENV_FILE}")" == "600" ]] || fail "${ENV_FILE} must have mode 600"
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
  for variable in SMART_AO_PUBLIC_HOST SMART_AO_DATABASE_URL SMART_AO_JWT_SIGNING_KEY SMART_AO_JWT_ISSUER SMART_AO_JWT_AUDIENCE POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD PGPASSWORD; do
    [[ -n "${!variable:-}" ]] || fail "${variable} is required"
    [[ "${!variable}" != REPLACE_WITH_* ]] || fail "${variable} still contains a placeholder"
  done
  [[ "${PGPASSWORD}" == "${POSTGRES_PASSWORD}" ]] || fail "PGPASSWORD must match POSTGRES_PASSWORD for the configured application role"
}

compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

validate() {
  require_command docker
  docker compose version >/dev/null
  load_environment
  compose config --quiet
  compose config | awk '/^[[:space:]]+image:/{print $2}' | while read -r image; do
    [[ "${image}" == *@sha256:* ]] || fail "unpinned image in resolved Compose: ${image}"
  done
  compose run --rm --no-deps caddy caddy validate --config /etc/caddy/Caddyfile >/dev/null
}

wait_postgres() {
  for attempt in $(seq 1 60); do
    if compose exec -T postgres pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  fail "PostgreSQL did not become ready within 120 seconds"
}

backup_database() {
  "${OPS_DIR}/backup-preprod.sh"
}

smoke() {
  require_command curl
  load_environment
  curl --fail --silent --show-error --max-time 10 "https://${SMART_AO_PUBLIC_HOST}/healthz/live" >/dev/null
  curl --fail --silent --show-error --max-time 10 "https://${SMART_AO_PUBLIC_HOST}/healthz/ready" >/dev/null
  compose ps --status running
}

deploy() {
  require_command flock
  validate
  exec 9>"${LOCK_FILE}"
  flock -n 9 || fail "another deployment is already running: ${LOCK_FILE}"
  compose pull caddy postgres clamav
  compose build --pull backend frontend
  compose up -d postgres clamav
  wait_postgres
  if compose exec -T postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -tAc "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = 'public'" | grep -q '^0$'; then
    [[ "${SMART_AO_ALLOW_EMPTY_BACKUP:-0}" == "1" ]] || fail "empty database detected; set SMART_AO_ALLOW_EMPTY_BACKUP=1 only for the reviewed first deployment"
  else
    backup_database
  fi
  compose run --rm backend alembic -c /app/backend/alembic.ini upgrade head
  compose up -d backend dce-retention-worker submission-export-webhook-worker frontend caddy
  smoke
  printf 'Deployment completed successfully. No automatic downgrade was attempted.\n'
}

status() {
  require_command docker
  load_environment
  compose ps
}

case "${1:-}" in
  config)
    validate
    ;;
  deploy)
    deploy
    ;;
  smoke)
    smoke
    ;;
  status)
    status
    ;;
  backup)
    "${OPS_DIR}/backup-preprod.sh"
    ;;
  restore)
    [[ -n "${2:-}" ]] || fail "restore requires a .sql.gz backup path"
    "${OPS_DIR}/restore-preprod.sh" "$2"
    ;;
  healthcheck)
    "${OPS_DIR}/healthcheck-preprod.sh"
    ;;
  rotate-key)
    "${OPS_DIR}/rotate-jwt-key-preprod.sh"
    ;;
  *)
    usage
    exit 2
    ;;
esac

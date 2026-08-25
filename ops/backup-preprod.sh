#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OPS_DIR="${ROOT_DIR}/ops"
ENV_FILE="${OPS_DIR}/.env.preprod"
COMPOSE_FILE="${OPS_DIR}/docker-compose.preprod.yml"
BACKUP_DIR="${SMART_AO_BACKUP_DIR:-/var/backups/smart-ao}"
RETENTION_DAYS="${SMART_AO_BACKUP_RETENTION_DAYS:-30}"

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

container_for_service() {
  compose ps -q "$1" 2>/dev/null | head -n 1
}

volume_mountpoint() {
  local container="$1" destination="$2" volume_name
  [[ -n "${container}" ]] || return 0
  volume_name="$(docker inspect "${container}" --format '{{range .Mounts}}{{if eq .Destination "'"${destination}"'"}}{{.Name}}{{end}}{{end}}')"
  [[ -n "${volume_name}" ]] || return 0
  docker volume inspect -f '{{.Mountpoint}}' "${volume_name}"
}

backup_volume() {
  local container="$1" destination="$2" output="$3" mountpoint
  mountpoint="$(volume_mountpoint "${container}" "${destination}")"
  if [[ -z "${mountpoint}" || ! -d "${mountpoint}" ]]; then
    if [[ "${SMART_AO_BACKUP_ALLOW_MISSING_VOLUMES:-0}" == "1" ]]; then
      printf 'WARNING: skipping absent volume %s by explicit override.\n' "${destination}" >&2
      return 0
    fi
    fail "expected persistent volume is not mounted: ${destination}"
  fi
  tar --numeric-owner --xattrs --acls -czf "${output}.tmp" -C "${mountpoint}" .
  mv -- "${output}.tmp" "${output}"
  chmod 600 "${output}"
}

main() {
  command -v docker >/dev/null 2>&1 || fail "docker is required"
  command -v gzip >/dev/null 2>&1 || fail "gzip is required"
  command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is required"
  command -v tar >/dev/null 2>&1 || fail "tar is required"
  load_environment
  [[ "${RETENTION_DAYS}" =~ ^[0-9]+$ ]] || fail "SMART_AO_BACKUP_RETENTION_DAYS must be an integer"
  install -d -m 700 "${BACKUP_DIR}"

  local timestamp sql_file backend_container caddy_container
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  sql_file="${BACKUP_DIR}/smart_ao_${timestamp}.sql.gz"
  backend_container="$(container_for_service backend)"
  caddy_container="$(container_for_service caddy)"

  compose exec -T postgres pg_dump --clean --if-exists --no-owner --no-privileges \
    -U "${POSTGRES_USER}" "${POSTGRES_DB}" | gzip -9 >"${sql_file}.tmp"
  mv -- "${sql_file}.tmp" "${sql_file}"
  chmod 600 "${sql_file}"

  backup_volume "${backend_container}" /var/lib/smart_ao/dce-quarantine \
    "${BACKUP_DIR}/smart_ao_${timestamp}.dce_quarantine.tar.gz"
  backup_volume "${caddy_container}" /data \
    "${BACKUP_DIR}/smart_ao_${timestamp}.caddy_data.tar.gz"
  backup_volume "${caddy_container}" /config \
    "${BACKUP_DIR}/smart_ao_${timestamp}.caddy_config.tar.gz"

  (
    cd "${BACKUP_DIR}"
    sha256sum "$(basename -- "${sql_file}")" smart_ao_${timestamp}.*.tar.gz 2>/dev/null \
      >"smart_ao_${timestamp}.sha256" || true
  )
  chmod 600 "${BACKUP_DIR}/smart_ao_${timestamp}.sha256"

  find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'smart_ao_*' \
    -mtime "+${RETENTION_DAYS}" -delete
  printf 'Backup completed: %s\n' "${timestamp}"
}

main "$@"

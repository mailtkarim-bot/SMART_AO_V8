#!/usr/bin/env bash
set -Eeuo pipefail

# Local-only PostgreSQL launcher for persistence and migration tests.
# It never removes containers/volumes and never prints the database password.

CONTAINER_NAME="${SMART_AO_POSTGRES_CONTAINER:-smart-ao-v8-postgres}"
VOLUME_NAME="${SMART_AO_POSTGRES_VOLUME:-smart-ao-v8-postgres-data}"
POSTGRES_IMAGE="${SMART_AO_POSTGRES_IMAGE:-postgres:16-alpine@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685}"
POSTGRES_DB="${SMART_AO_TEST_DB_NAME:-smart_ao}"
POSTGRES_USER="${SMART_AO_TEST_DB_USER:-smart_ao}"
POSTGRES_PASSWORD="${SMART_AO_TEST_DB_PASSWORD:-smart_ao}"
HOST_PORT="${SMART_AO_TEST_DB_PORT:-5433}"
WAIT_SECONDS="${SMART_AO_POSTGRES_WAIT_SECONDS:-90}"

usage() {
  cat <<'EOF'
Usage: scripts/start_local_postgres.sh [--help]

Starts or reuses an isolated local PostgreSQL 16 container for SMART_AO tests.
The container and volume are never removed by this script.

Environment overrides:
  SMART_AO_POSTGRES_CONTAINER  Container name (default: smart-ao-v8-postgres)
  SMART_AO_POSTGRES_VOLUME     Docker volume (default: smart-ao-v8-postgres-data)
  SMART_AO_POSTGRES_IMAGE      Image reference (default: pinned postgres:16-alpine digest)
  SMART_AO_TEST_DB_NAME        Database name (default: smart_ao)
  SMART_AO_TEST_DB_USER        Database user (default: smart_ao)
  SMART_AO_TEST_DB_PASSWORD    Local-only password (default: smart_ao)
  SMART_AO_TEST_DB_PORT        Host port (default: 5433)
  SMART_AO_POSTGRES_WAIT_SECONDS  Healthcheck timeout (default: 90)

After startup, run tests with a password supplied separately, for example:
  SMART_AO_TEST_DATABASE_URL='postgresql+psycopg://smart_ao:<password>@127.0.0.1:5433/smart_ao' \
    uv run pytest -m db
EOF
}

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi
[[ "$#" -eq 0 ]] || fail "unknown argument: $1 (use --help)"

command -v docker >/dev/null 2>&1 || fail "Docker CLI is required"

valid_identifier() {
  [[ "$1" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]
}

valid_docker_name() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]]
}

valid_docker_name "$CONTAINER_NAME" || fail "invalid container name"
valid_docker_name "$VOLUME_NAME" || fail "invalid volume name"
valid_identifier "$POSTGRES_DB" || fail "invalid database name"
valid_identifier "$POSTGRES_USER" || fail "invalid database user"
[[ "$HOST_PORT" =~ ^[0-9]+$ ]] || fail "SMART_AO_TEST_DB_PORT must be numeric"
(( HOST_PORT >= 1 && HOST_PORT <= 65535 )) || fail "host port must be between 1 and 65535"
[[ "$WAIT_SECONDS" =~ ^[0-9]+$ ]] || fail "SMART_AO_POSTGRES_WAIT_SECONDS must be numeric"
(( WAIT_SECONDS >= 1 && WAIT_SECONDS <= 3600 )) || fail "wait timeout must be between 1 and 3600 seconds"
[[ -n "$POSTGRES_PASSWORD" ]] || fail "SMART_AO_TEST_DB_PASSWORD must not be empty"

container_exists=0
if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  container_exists=1
  mapped_port="$(docker port "$CONTAINER_NAME" 5432/tcp 2>/dev/null || true)"
  [[ "$mapped_port" == *":${HOST_PORT}"* ]] || fail "existing container does not expose PostgreSQL on host port ${HOST_PORT}; choose another SMART_AO_POSTGRES_CONTAINER or SMART_AO_TEST_DB_PORT"
  state="$(docker inspect --format '{{.State.Status}}' "$CONTAINER_NAME")"
  if [[ "$state" != "running" ]]; then
    printf 'Starting existing PostgreSQL container %s.\n' "$CONTAINER_NAME"
    docker start "$CONTAINER_NAME" >/dev/null
  else
    printf 'Reusing running PostgreSQL container %s.\n' "$CONTAINER_NAME"
  fi
else
  docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1 || docker volume create "$VOLUME_NAME" >/dev/null
  printf 'Creating PostgreSQL container %s.\n' "$CONTAINER_NAME"
  docker run --detach \
    --name "$CONTAINER_NAME" \
    --label com.smart-ao.role=local-test-database \
    --publish "${HOST_PORT}:5432" \
    --env "POSTGRES_DB=${POSTGRES_DB}" \
    --env "POSTGRES_USER=${POSTGRES_USER}" \
    --env "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
    --health-cmd="pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}" \
    --health-interval=5s \
    --health-timeout=5s \
    --health-retries=20 \
    --volume "${VOLUME_NAME}:/var/lib/postgresql/data" \
    "$POSTGRES_IMAGE" >/dev/null
fi

for (( elapsed = 0; elapsed < WAIT_SECONDS; elapsed++ )); do
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}starting{{end}}' "$CONTAINER_NAME" 2>/dev/null || true)"
  if [[ "$health" == "healthy" ]]; then
    printf 'PostgreSQL is healthy on 127.0.0.1:%s (database=%s, user=%s).\n' \
      "$HOST_PORT" "$POSTGRES_DB" "$POSTGRES_USER"
    printf 'The password is intentionally not displayed.\n'
    exit 0
  fi
  if [[ "$health" == "unhealthy" ]]; then
    printf 'PostgreSQL healthcheck is unhealthy; inspect with: docker logs %s\n' "$CONTAINER_NAME" >&2
    exit 1
  fi
  sleep 1
done

printf 'PostgreSQL did not become healthy within %s seconds; inspect with: docker logs %s\n' \
  "$WAIT_SECONDS" "$CONTAINER_NAME" >&2
exit 1

#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OPS_DIR="${ROOT_DIR}/ops"
COMPOSE_FILE="${OPS_DIR}/docker-compose.preprod.yml"
SIM_ENV="${OPS_DIR}/.env.preprod"
MODE="${1:---static-only}"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

pass() {
  printf 'PASS: %s\n' "$*"
}

usage() {
  cat <<'EOF'
Usage: scripts/simulate_staging_deploy.sh [--static-only|--compose-config]

Modes:
  --static-only      Validate the staging template without Docker or secrets.
  --compose-config   Create an ephemeral dummy env file and run docker compose
                     config --quiet. This never builds, pulls, or starts services.
EOF
}

[[ -f "${COMPOSE_FILE}" ]] || fail "missing ${COMPOSE_FILE}"
[[ -f "${OPS_DIR}/Caddyfile" ]] || fail "missing ${OPS_DIR}/Caddyfile"
[[ -f "${OPS_DIR}/docker/backend.Dockerfile" ]] || fail "missing backend Dockerfile"
[[ -f "${OPS_DIR}/docker/frontend.Dockerfile" ]] || fail "missing frontend Dockerfile"

# These checks intentionally inspect text only. They do not source .env.preprod.
grep -q '^services:' "${COMPOSE_FILE}" || fail "Compose services section is missing"
grep -q '^  backend:' "${COMPOSE_FILE}" || fail "backend service is missing"
grep -q '^  frontend:' "${COMPOSE_FILE}" || fail "frontend service is missing"
grep -q '^  postgres:' "${COMPOSE_FILE}" || fail "postgres service is missing"
grep -q '^  clamav:' "${COMPOSE_FILE}" || fail "clamav service is missing"
grep -q '^  dce-retention-worker:' "${COMPOSE_FILE}" || fail "DCE retention worker is missing"
grep -q '^  submission-export-webhook-worker:' "${COMPOSE_FILE}" || fail "submission webhook worker is missing"
grep -q 'internal: true' "${COMPOSE_FILE}" || fail "internal Docker network is missing"
grep -q 'healthcheck:' "${COMPOSE_FILE}" || fail "healthchecks are missing"
grep -q '80:80' "${COMPOSE_FILE}" || fail "HTTP edge port is missing"
grep -q '443:443' "${COMPOSE_FILE}" || fail "HTTPS edge port is missing"

if grep -Eq '(^|[[:space:]-])(3310|5432|8000):' "${COMPOSE_FILE}"; then
  fail "private PostgreSQL, API, or ClamAV ports are published"
fi

for dockerfile in "${OPS_DIR}/docker/backend.Dockerfile" "${OPS_DIR}/docker/frontend.Dockerfile"; do
  grep -q '@sha256:' "${dockerfile}" || fail "unpinned base image in ${dockerfile}"
done
image_count="$(grep -c '@sha256:' "${COMPOSE_FILE}" || true)"
(( image_count >= 3 )) || fail "expected at least three digest-pinned Compose images"

pass "staging template structure, private networking, workers, healthchecks, and edge ports"
pass "Dockerfile and Compose image digests are present"

case "${MODE}" in
  --static-only)
    pass "static simulation completed without Docker, production env, build, pull, or startup"
    ;;
  --compose-config)
    command -v docker >/dev/null 2>&1 || fail "docker is required for --compose-config"
    docker compose version >/dev/null 2>&1 || fail "docker compose plugin is required for --compose-config"
    [[ ! -e "${SIM_ENV}" ]] || fail "refusing to overwrite existing ${SIM_ENV}; use --static-only"
    trap 'rm -f "${SIM_ENV}"' EXIT
    umask 077
    cat >"${SIM_ENV}" <<'EOF'
SMART_AO_PUBLIC_HOST=staging.invalid
SMART_AO_DATABASE_URL=postgresql+psycopg://simulation:simulation@postgres:5432/simulation
SMART_AO_JWT_SIGNING_KEY=simulation-only-key-not-for-runtime
SMART_AO_JWT_ISSUER=smart-ao-simulation
SMART_AO_JWT_AUDIENCE=smart-ao-simulation
POSTGRES_DB=simulation
POSTGRES_USER=simulation
POSTGRES_PASSWORD=simulation
PGPASSWORD=simulation
SMART_AO_ALLOW_EMPTY_BACKUP=1
EOF
    chmod 600 "${SIM_ENV}"
    docker compose --env-file "${SIM_ENV}" -f "${COMPOSE_FILE}" config --quiet
    pass "docker compose config resolved with ephemeral non-production values"
    pass "no Docker image was built, pulled, or started"
    ;;
  -h|--help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

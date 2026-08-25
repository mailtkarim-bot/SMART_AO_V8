#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${SMART_AO_DCE_ENV_FILE:-${ROOT_DIR}/ops/.env.preprod}"
COMPOSE_FILE="${SMART_AO_DCE_COMPOSE_FILE:-${ROOT_DIR}/ops/docker-compose.preprod.yml}"
PROJECT_NAME="${SMART_AO_PROJECT_NAME:-smart-ao-preprod}"

if [[ $# -ne 2 ]]; then
  echo "usage: $0 TENANT_ID DCE_VERSION_ID" >&2
  exit 64
fi

tenant_id="$1"
dce_version_id="$2"

if [[ ! "$tenant_id" =~ ^[0-9a-fA-F-]{36}$ ]]; then
  echo "invalid tenant UUID" >&2
  exit 64
fi
if [[ ! "$dce_version_id" =~ ^[0-9a-fA-F-]{36}$ ]]; then
  echo "invalid DCE version UUID" >&2
  exit 64
fi

[[ -f "$ENV_FILE" ]] || {
  echo "missing preproduction env file: $ENV_FILE" >&2
  exit 78
}
[[ "$(stat -c '%a' "$ENV_FILE")" == "600" ]] || {
  echo "preproduction env file must have mode 600" >&2
  exit 78
}

exec docker compose --env-file "$ENV_FILE" -p "$PROJECT_NAME" -f "$COMPOSE_FILE" \
  --profile dce-analysis run --rm --no-deps --no-ansi dce-rc-analysis-runner \
  python -m app.workers.dce_analysis \
  --tenant-id "$tenant_id" \
  --dce-version-id "$dce_version_id"

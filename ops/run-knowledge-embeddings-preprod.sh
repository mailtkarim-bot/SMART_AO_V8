#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${SMART_AO_KNOWLEDGE_ENV_FILE:-${ROOT_DIR}/ops/.env.preprod}"
COMPOSE_FILE="${SMART_AO_KNOWLEDGE_COMPOSE_FILE:-${ROOT_DIR}/ops/docker-compose.preprod.yml}"
PROJECT_NAME="${SMART_AO_PROJECT_NAME:-smart-ao-preprod}"

if [[ $# -ne 3 ]]; then
  echo "usage: $0 TENANT_ID CASE_ID DCE_VERSION_ID" >&2
  exit 64
fi

tenant_id="$1"
case_id="$2"
dce_version_id="$3"

for value_name in tenant_id case_id dce_version_id; do
  value="${!value_name}"
  if [[ ! "$value" =~ ^[0-9a-fA-F-]{36}$ ]]; then
    echo "invalid ${value_name} UUID" >&2
    exit 64
  fi
done

[[ -f "$ENV_FILE" ]] || {
  echo "missing preproduction env file: $ENV_FILE" >&2
  exit 78
}
[[ "$(stat -c '%a' "$ENV_FILE")" == "600" ]] || {
  echo "preproduction env file must have mode 600" >&2
  exit 78
}

exec docker compose --env-file "$ENV_FILE" -p "$PROJECT_NAME" -f "$COMPOSE_FILE" \
  run --rm --no-deps --no-ansi backend \
  python -m app.workers.knowledge_embeddings \
  --tenant-id "$tenant_id" \
  --case-id "$case_id" \
  --dce-version-id "$dce_version_id"

# The worker itself requires SMART_AO_RAG_ENABLED=1 and
# SMART_AO_RAG_INDEXING_ENABLED=1 in the protected runtime environment.
# It remains a one-shot operator action until a measured automatic trigger is approved.


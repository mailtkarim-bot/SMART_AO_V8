#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OPS_DIR="${ROOT_DIR}/ops"
COMPOSE_FILE="${OPS_DIR}/docker-compose.preprod.yml"
MANIFEST_FILE="${OPS_DIR}/golden-corpus/manifest.example.json"

pass_count=0
skip_count=0

pass_check() {
  printf 'PASS %s\n' "$1"
  pass_count=$((pass_count + 1))
}

skip_check() {
  printf 'SKIP %s\n' "$1"
  skip_count=$((skip_count + 1))
}

fail() {
  printf 'FAIL %s\n' "$1" >&2
  exit 1
}

[[ -f "${COMPOSE_FILE}" ]] || fail "preproduction compose file is missing"
[[ -f "${MANIFEST_FILE}" ]] || fail "golden corpus example manifest is missing"
pass_check "required repository contracts exist"

if command -v docker >/dev/null 2>&1; then
  docker compose -f "${COMPOSE_FILE}" config >/dev/null \
    || fail "preproduction compose configuration is invalid"
  pass_check "docker compose configuration"
else
  skip_check "docker unavailable: compose validation deferred to VPS/preproduction"
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHONPATH="${ROOT_DIR}/backend" python3 -m app.platform.quality.golden_corpus "${MANIFEST_FILE}" \
    >/dev/null \
    || fail "golden corpus manifest validation failed"
  pass_check "golden corpus manifest"
else
  skip_check "python3 unavailable: golden corpus validation deferred"
fi

if [[ "${SMART_AO_PUBLIC_HOST:-}" != "" ]]; then
  case "${SMART_AO_PUBLIC_HOST}" in
    localhost|127.0.0.1|0.0.0.0) fail "public host must not be a loopback address" ;;
  esac
  command -v curl >/dev/null 2>&1 || fail "curl is required when SMART_AO_PUBLIC_HOST is set"
  curl --fail --silent --show-error --max-time 10 \
    "https://${SMART_AO_PUBLIC_HOST}/healthz/live" >/dev/null \
    || fail "public HTTPS liveness check failed"
  pass_check "public HTTPS liveness"
else
  skip_check "SMART_AO_PUBLIC_HOST unset: public HTTPS check deferred to VPS/preproduction"
fi

if grep -Eq '3310:[0-9]' "${COMPOSE_FILE}"; then
  fail "ClamAV port 3310 must not be published"
fi
pass_check "ClamAV port is not published in compose"

printf 'SUMMARY pass=%d skip=%d\n' "${pass_count}" "${skip_count}"

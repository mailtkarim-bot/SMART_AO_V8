#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/ops/.env.preprod"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ "${SMART_AO_CONFIRM_ROTATE:-}" == "YES" ]] || fail "set SMART_AO_CONFIRM_ROTATE=YES for an explicit key rotation"
[[ -f "${ENV_FILE}" ]] || fail "missing ${ENV_FILE}"
[[ "$(stat -c '%a' "${ENV_FILE}")" == "600" ]] || fail "${ENV_FILE} must have mode 600"
command -v openssl >/dev/null 2>&1 || fail "openssl is required"

if [[ -n "${SMART_AO_NEW_JWT_SIGNING_KEY:-}" ]]; then
  new_key="${SMART_AO_NEW_JWT_SIGNING_KEY}"
elif [[ -t 0 ]]; then
  read -r -s -p "New JWT signing key (at least 32 random bytes): " new_key
  printf '\n'
else
  fail "provide SMART_AO_NEW_JWT_SIGNING_KEY through a protected operator environment"
fi
[[ "${#new_key}" -ge 32 ]] || fail "new JWT signing key is too short"
[[ "${new_key}" != REPLACE_WITH_* ]] || fail "new JWT signing key is a placeholder"

rotation_id="preprod-$(date -u +%Y%m%dT%H%M%SZ)"
tmp_file="$(mktemp "${ENV_FILE}.rotation.XXXXXX")"
trap 'rm -f -- "${tmp_file}"' EXIT
ROTATION_KEY="${new_key}" ROTATION_ID="${rotation_id}" awk '
  /^SMART_AO_JWT_SIGNING_KEY=/ { print "SMART_AO_JWT_SIGNING_KEY=" ENVIRON["ROTATION_KEY"]; next }
  /^SMART_AO_JWT_KEY_ROTATION_ID=/ { print "SMART_AO_JWT_KEY_ROTATION_ID=" ENVIRON["ROTATION_ID"]; next }
  { print }
' "${ENV_FILE}" >"${tmp_file}"
chmod 600 "${tmp_file}"
mv -f -- "${tmp_file}" "${ENV_FILE}"
unset new_key SMART_AO_NEW_JWT_SIGNING_KEY ROTATION_KEY
printf 'JWT signing key rotated atomically; rotation id=%s. Restart the stack in the approved maintenance window.\n' "${rotation_id}"

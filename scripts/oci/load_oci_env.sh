#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

load_env_file() {
  local env_file="$1"
  if [[ ! -f "$env_file" ]]; then
    return 0
  fi

  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    local line key value
    line="${raw_line#"${raw_line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    if [[ -z "$line" || "$line" == \#* || "$line" != *=* ]]; then
      continue
    fi
    key="${line%%=*}"
    value="${line#*=}"
    key="${key//[[:space:]]/}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    if [[ -n "$key" ]]; then
      export "$key=$value"
    fi
  done < "$env_file"
}

load_env_file "$ROOT_DIR/.env"
load_env_file "$ROOT_DIR/.env.oci"

OCI_BIN="${OCI_BIN:-}"
if [[ -z "$OCI_BIN" ]]; then
  if [[ -x "$ROOT_DIR/.venv-oci/bin/oci" ]]; then
    OCI_BIN="$ROOT_DIR/.venv-oci/bin/oci"
  else
    OCI_BIN="oci"
  fi
fi

OCI_AUTH_MODE="${OCI_AUTH_MODE:-${OCI_CLI_AUTH:-api_key}}"
OCI_CLI_PROFILE="${OCI_CLI_PROFILE:-GIROFY}"

require_env() {
  local missing=0
  for name in "$@"; do
    if [[ -z "${!name:-}" ]]; then
      echo "Falta configurar $name no .env ou .env.oci" >&2
      missing=1
    fi
  done
  return "$missing"
}

require_oci_cli() {
  if ! command -v "$OCI_BIN" >/dev/null 2>&1; then
    echo "OCI CLI não encontrado. Instale com: python3 -m venv .venv-oci && .venv-oci/bin/python -m pip install oci-cli" >&2
    exit 1
  fi
}

require_oci_auth_env() {
  if [[ "$OCI_AUTH_MODE" == "security_token" ]]; then
    require_env OCI_CLI_REGION OCI_COMPARTMENT_ID
    return
  fi

  require_env \
    OCI_CLI_TENANCY \
    OCI_CLI_USER \
    OCI_CLI_FINGERPRINT \
    OCI_CLI_KEY_FILE \
    OCI_CLI_REGION \
    OCI_COMPARTMENT_ID
}

oci_config_file() {
  local config_file="${OCI_CONFIG_FILE:-$ROOT_DIR/.oci/generated-config}"
  mkdir -p "$(dirname "$config_file")"
  chmod 700 "$(dirname "$config_file")"
  cat > "$config_file" <<CFG
[DEFAULT]
user=${OCI_CLI_USER}
fingerprint=${OCI_CLI_FINGERPRINT}
tenancy=${OCI_CLI_TENANCY}
region=${OCI_CLI_REGION}
key_file=${OCI_CLI_KEY_FILE}
CFG
  chmod 600 "$config_file"
  echo "$config_file"
}

oci_cli() {
  require_oci_cli

  if [[ "$OCI_AUTH_MODE" == "security_token" ]]; then
    local session_config_file="${OCI_CONFIG_FILE:-$HOME/.oci/config}"
    env \
      -u OCI_CLI_TENANCY \
      -u OCI_CLI_USER \
      -u OCI_CLI_FINGERPRINT \
      -u OCI_CLI_KEY_FILE \
      "$OCI_BIN" --config-file "$session_config_file" --profile "$OCI_CLI_PROFILE" --auth security_token "$@"
    return
  fi

  local config_file
  config_file="$(oci_config_file)"
  "$OCI_BIN" --config-file "$config_file" "$@"
}

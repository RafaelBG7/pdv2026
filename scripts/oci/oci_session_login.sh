#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/load_oci_env.sh"

require_oci_cli
require_env OCI_CLI_REGION

OCI_CLI_PROFILE="${OCI_CLI_PROFILE:-GIROFY}"
OCI_SESSION_EXPIRATION_MINUTES="${OCI_SESSION_EXPIRATION_MINUTES:-60}"
OCI_SESSION_TOKEN_LOCATION="${OCI_SESSION_TOKEN_LOCATION:-$HOME/.oci/sessions}"
OCI_CONFIG_FILE="${OCI_CONFIG_FILE:-$HOME/.oci/config}"

mkdir -p "$OCI_SESSION_TOKEN_LOCATION" "$(dirname "$OCI_CONFIG_FILE")"
chmod 700 "$OCI_SESSION_TOKEN_LOCATION" "$(dirname "$OCI_CONFIG_FILE")"

echo "Abrindo login da Oracle Cloud para o perfil $OCI_CLI_PROFILE..."
env \
  -u OCI_CLI_TENANCY \
  -u OCI_CLI_USER \
  -u OCI_CLI_FINGERPRINT \
  -u OCI_CLI_KEY_FILE \
  "$OCI_BIN" session authenticate \
  --region "$OCI_CLI_REGION" \
  --profile-name "$OCI_CLI_PROFILE" \
  --config-location "$OCI_CONFIG_FILE" \
  --token-location "$OCI_SESSION_TOKEN_LOCATION" \
  --session-expiration-in-minutes "$OCI_SESSION_EXPIRATION_MINUTES"

cat <<OUT

Sessão OCI criada.

Para usar os scripts com esta sessão, mantenha no .env:
OCI_AUTH_MODE=security_token
OCI_CLI_PROFILE=$OCI_CLI_PROFILE
OCI_CLI_REGION=$OCI_CLI_REGION
OCI_CONFIG_FILE=$OCI_CONFIG_FILE

Valide com:
rtk scripts/oci/oci_check.sh
OUT

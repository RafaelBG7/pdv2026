#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/load_oci_env.sh"

require_oci_cli
require_oci_auth_env

if [[ "$OCI_AUTH_MODE" != "security_token" && ! -f "$OCI_CLI_KEY_FILE" ]]; then
  echo "Arquivo da private key não encontrado: $OCI_CLI_KEY_FILE" >&2
  exit 1
fi

echo "OCI CLI: $("$OCI_BIN" --version)"
echo "Autenticação: $OCI_AUTH_MODE"
if [[ "$OCI_AUTH_MODE" == "security_token" ]]; then
  echo "Perfil: $OCI_CLI_PROFILE"
fi
echo "Região: $OCI_CLI_REGION"
echo "Compartment: $OCI_COMPARTMENT_ID"
echo
echo "Validando autenticação..."
oci_cli iam region list --output table >/dev/null
echo "Autenticação OCI OK."

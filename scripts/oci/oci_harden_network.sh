#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/load_oci_env.sh"

require_oci_auth_env

OCI_PROJECT_PREFIX="${OCI_PROJECT_PREFIX:-girofy}"
OCI_ALLOWED_SSH_CIDR="${OCI_ALLOWED_SSH_CIDR:-}"
OCI_ALLOWED_HTTP_CIDR="${OCI_ALLOWED_HTTP_CIDR:-0.0.0.0/0}"
OCI_PUBLIC_HTTP_PORT="${OCI_PUBLIC_HTTP_PORT:-18080}"

require_env OCI_ALLOWED_SSH_CIDR OCI_ALLOWED_HTTP_CIDR

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

VCN_ID="$(
  oci_cli network vcn list \
    --compartment-id "$OCI_COMPARTMENT_ID" \
    --display-name "$OCI_PROJECT_PREFIX-vcn" \
    --all \
    --query 'data[0].id' \
    --raw-output
)"

if [[ -z "$VCN_ID" || "$VCN_ID" == "null" ]]; then
  echo "VCN $OCI_PROJECT_PREFIX-vcn não encontrada." >&2
  exit 1
fi

SECURITY_LIST_ID="$(
  oci_cli network security-list list \
    --compartment-id "$OCI_COMPARTMENT_ID" \
    --vcn-id "$VCN_ID" \
    --display-name "$OCI_PROJECT_PREFIX-public-sl" \
    --all \
    --query 'data[0].id' \
    --raw-output
)"

if [[ -z "$SECURITY_LIST_ID" || "$SECURITY_LIST_ID" == "null" ]]; then
  echo "Security List $OCI_PROJECT_PREFIX-public-sl não encontrada." >&2
  exit 1
fi

cat > "$TMP_DIR/ingress.json" <<JSON
[
  {
    "source": "$OCI_ALLOWED_SSH_CIDR",
    "protocol": "6",
    "tcpOptions": {
      "destinationPortRange": {
        "min": 22,
        "max": 22
      }
    }
  },
  {
    "source": "$OCI_ALLOWED_HTTP_CIDR",
    "protocol": "6",
    "tcpOptions": {
      "destinationPortRange": {
        "min": $OCI_PUBLIC_HTTP_PORT,
        "max": $OCI_PUBLIC_HTTP_PORT
      }
    }
  }
]
JSON

oci_cli network security-list update \
  --security-list-id "$SECURITY_LIST_ID" \
  --ingress-security-rules "file://$TMP_DIR/ingress.json" \
  --force \
  --wait-for-state AVAILABLE >/dev/null

cat <<OUT
Rede OCI endurecida.

Entrada permitida:
- SSH 22: $OCI_ALLOWED_SSH_CIDR
- Girofy $OCI_PUBLIC_HTTP_PORT: $OCI_ALLOWED_HTTP_CIDR

Portas 80 e 443 não ficam liberadas neste modo de teste.
OUT

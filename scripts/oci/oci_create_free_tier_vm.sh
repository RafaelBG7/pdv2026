#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/load_oci_env.sh"

require_oci_auth_env
require_env OCI_AVAILABILITY_DOMAIN OCI_SSH_PUBLIC_KEY_FILE

OCI_PROJECT_PREFIX="${OCI_PROJECT_PREFIX:-girofy}"
OCI_VCN_CIDR="${OCI_VCN_CIDR:-10.10.0.0/16}"
OCI_SUBNET_CIDR="${OCI_SUBNET_CIDR:-10.10.1.0/24}"
OCI_ALLOWED_SSH_CIDR="${OCI_ALLOWED_SSH_CIDR:-0.0.0.0/0}"
OCI_ALLOWED_HTTP_CIDR="${OCI_ALLOWED_HTTP_CIDR:-0.0.0.0/0}"
OCI_PUBLIC_HTTP_PORT="${OCI_PUBLIC_HTTP_PORT:-18080}"
OCI_SHAPE="${OCI_SHAPE:-VM.Standard.A1.Flex}"
OCI_OCPUS="${OCI_OCPUS:-1}"
OCI_MEMORY_GB="${OCI_MEMORY_GB:-6}"
OCI_BOOT_VOLUME_GB="${OCI_BOOT_VOLUME_GB:-50}"
OCI_INSTANCE_NAME="${OCI_INSTANCE_NAME:-girofy-app-01}"
OCI_IMAGE_OS="${OCI_IMAGE_OS:-Canonical Ubuntu}"
OCI_IMAGE_OS_VERSION="${OCI_IMAGE_OS_VERSION:-22.04}"

if [[ ! -f "$OCI_SSH_PUBLIC_KEY_FILE" ]]; then
  echo "Arquivo da chave pública SSH não encontrado: $OCI_SSH_PUBLIC_KEY_FILE" >&2
  exit 1
fi

if [[ "$OCI_ALLOWED_SSH_CIDR" == *"SEU_IP_PUBLICO"* ]]; then
  echo "Configure OCI_ALLOWED_SSH_CIDR com seu IP público no formato X.X.X.X/32 antes de criar a rede." >&2
  exit 1
fi

if [[ "$OCI_BOOT_VOLUME_GB" -gt 50 ]]; then
  echo "Para manter Free Tier conservador, OCI_BOOT_VOLUME_GB não deve passar de 50 neste script." >&2
  exit 1
fi

echo "Criando rede Free Tier do Girofy em $OCI_CLI_REGION..."

VCN_ID="$(
  oci_cli network vcn create \
    --compartment-id "$OCI_COMPARTMENT_ID" \
    --display-name "$OCI_PROJECT_PREFIX-vcn" \
    --cidr-block "$OCI_VCN_CIDR" \
    --query 'data.id' \
    --raw-output
)"

IGW_ID="$(
  oci_cli network internet-gateway create \
    --compartment-id "$OCI_COMPARTMENT_ID" \
    --vcn-id "$VCN_ID" \
    --is-enabled true \
    --display-name "$OCI_PROJECT_PREFIX-igw" \
    --query 'data.id' \
    --raw-output
)"

ROUTE_TABLE_ID="$(
  oci_cli network route-table create \
    --compartment-id "$OCI_COMPARTMENT_ID" \
    --vcn-id "$VCN_ID" \
    --display-name "$OCI_PROJECT_PREFIX-public-rt" \
    --route-rules "[{\"cidrBlock\":\"0.0.0.0/0\",\"networkEntityId\":\"$IGW_ID\"}]" \
    --query 'data.id' \
    --raw-output
)"

SECURITY_LIST_ID="$(
  oci_cli network security-list create \
    --compartment-id "$OCI_COMPARTMENT_ID" \
    --vcn-id "$VCN_ID" \
    --display-name "$OCI_PROJECT_PREFIX-public-sl" \
    --egress-security-rules '[{"destination":"0.0.0.0/0","protocol":"all"}]' \
    --ingress-security-rules "[{\"source\":\"$OCI_ALLOWED_SSH_CIDR\",\"protocol\":\"6\",\"tcpOptions\":{\"destinationPortRange\":{\"min\":22,\"max\":22}}},{\"source\":\"$OCI_ALLOWED_HTTP_CIDR\",\"protocol\":\"6\",\"tcpOptions\":{\"destinationPortRange\":{\"min\":$OCI_PUBLIC_HTTP_PORT,\"max\":$OCI_PUBLIC_HTTP_PORT}}}]" \
    --query 'data.id' \
    --raw-output
)"

SUBNET_ID="$(
  oci_cli network subnet create \
    --compartment-id "$OCI_COMPARTMENT_ID" \
    --vcn-id "$VCN_ID" \
    --display-name "$OCI_PROJECT_PREFIX-public-subnet" \
    --cidr-block "$OCI_SUBNET_CIDR" \
    --route-table-id "$ROUTE_TABLE_ID" \
    --security-list-ids "[\"$SECURITY_LIST_ID\"]" \
    --prohibit-public-ip-on-vnic false \
    --query 'data.id' \
    --raw-output
)"

echo "Buscando imagem $OCI_IMAGE_OS $OCI_IMAGE_OS_VERSION para $OCI_SHAPE..."
IMAGE_ID="$(
  oci_cli compute image list \
    --compartment-id "$OCI_COMPARTMENT_ID" \
    --shape "$OCI_SHAPE" \
    --operating-system "$OCI_IMAGE_OS" \
    --operating-system-version "$OCI_IMAGE_OS_VERSION" \
    --sort-by TIMECREATED \
    --sort-order DESC \
    --all \
    --query 'data[0].id' \
    --raw-output
)"

if [[ -z "$IMAGE_ID" || "$IMAGE_ID" == "null" ]]; then
  echo "Não encontrei imagem compatível. Ajuste OCI_IMAGE_OS/OCI_IMAGE_OS_VERSION." >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cat > "$TMP_DIR/shape-config.json" <<JSON
{
  "ocpus": $OCI_OCPUS,
  "memoryInGBs": $OCI_MEMORY_GB
}
JSON

CLOUD_INIT_FILE="${OCI_CLOUD_INIT_FILE:-$ROOT_DIR/scripts/oci/cloud-init-girofy.yaml}"

echo "Criando VM Always Free candidata: $OCI_INSTANCE_NAME"
LAUNCH_ARGS=(
  compute instance launch
  --compartment-id "$OCI_COMPARTMENT_ID"
  --availability-domain "$OCI_AVAILABILITY_DOMAIN"
  --display-name "$OCI_INSTANCE_NAME"
  --shape "$OCI_SHAPE"
  --image-id "$IMAGE_ID"
  --subnet-id "$SUBNET_ID"
  --assign-public-ip true
  --boot-volume-size-in-gbs "$OCI_BOOT_VOLUME_GB"
  --ssh-authorized-keys-file "$OCI_SSH_PUBLIC_KEY_FILE"
  --user-data-file "$CLOUD_INIT_FILE"
)

if [[ "$OCI_SHAPE" == *.Flex ]]; then
  LAUNCH_ARGS+=(--shape-config "file://$TMP_DIR/shape-config.json")
fi

INSTANCE_JSON="$(
  oci_cli "${LAUNCH_ARGS[@]}"
)"

INSTANCE_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["id"])' <<< "$INSTANCE_JSON")"

echo "Aguardando IP público..."
sleep 15
PUBLIC_IP="$(
  oci_cli compute instance list-vnics \
    --instance-id "$INSTANCE_ID" \
    --query 'data[0]."public-ip"' \
    --raw-output
)"

cat <<OUT

Ambiente OCI criado.

VCN: $VCN_ID
Subnet: $SUBNET_ID
Instance: $INSTANCE_ID
IP público: $PUBLIC_IP

Próximo passo:
ssh ubuntu@$PUBLIC_IP

Depois envie o projeto para /opt/girofy/app e rode:
cd /opt/girofy/app
docker compose -f docker-compose.oci.yml up -d --build
OUT

#!/usr/bin/env bash
set -euo pipefail

GITHUB_REPOSITORY_URL="${GITHUB_REPOSITORY_URL:-}"
GITHUB_RUNNER_TOKEN="${GITHUB_RUNNER_TOKEN:-}"
RUNNER_DIR="${RUNNER_DIR:-/opt/actions-runner-girofy}"
RUNNER_NAME="${RUNNER_NAME:-girofy-oci}"
RUNNER_LABELS="${RUNNER_LABELS:-girofy-oci}"
RUNNER_SERVICE_USER="${RUNNER_SERVICE_USER:-$(id -un)}"

if [[ -z "$GITHUB_REPOSITORY_URL" || -z "$GITHUB_RUNNER_TOKEN" ]]; then
  cat >&2 <<'OUT'
Configure:
GITHUB_REPOSITORY_URL=https://github.com/SEU_USUARIO/SEU_REPOSITORIO
GITHUB_RUNNER_TOKEN=TOKEN_DO_GITHUB
OUT
  exit 1
fi

case "$(uname -m)" in
  x86_64|amd64) RUNNER_ARCH="x64" ;;
  aarch64|arm64) RUNNER_ARCH="arm64" ;;
  *) echo "Arquitetura não suportada: $(uname -m)" >&2; exit 1 ;;
esac

RUNNER_VERSION="${GITHUB_RUNNER_VERSION:-$(
  python3 - <<'PY'
import json
import urllib.request

with urllib.request.urlopen('https://api.github.com/repos/actions/runner/releases/latest') as response:
    data = json.load(response)
print(data['tag_name'].lstrip('v'))
PY
)}"

sudo mkdir -p "$RUNNER_DIR"
sudo chown "$RUNNER_SERVICE_USER":"$RUNNER_SERVICE_USER" "$RUNNER_DIR"
cd "$RUNNER_DIR"

if [[ ! -f config.sh ]]; then
  curl -fL -o actions-runner.tar.gz \
    "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
  tar xzf actions-runner.tar.gz
  rm actions-runner.tar.gz
fi

if [[ -f .runner ]]; then
  ./config.sh remove --unattended --token "$GITHUB_RUNNER_TOKEN" || true
fi

./config.sh \
  --url "$GITHUB_REPOSITORY_URL" \
  --token "$GITHUB_RUNNER_TOKEN" \
  --name "$RUNNER_NAME" \
  --labels "$RUNNER_LABELS" \
  --unattended \
  --replace

sudo ./svc.sh install "$RUNNER_SERVICE_USER"
sudo ./svc.sh start
sudo ./svc.sh status

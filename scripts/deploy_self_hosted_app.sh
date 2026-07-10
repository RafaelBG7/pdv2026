#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OCI_DEPLOY_PATH="${OCI_DEPLOY_PATH:-/opt/girofy/app}"
OCI_DEPLOY_PORT="${OCI_DEPLOY_PORT:-18080}"

if [[ -z "$OCI_DEPLOY_PATH" ]]; then
  echo "Configure OCI_DEPLOY_PATH." >&2
  exit 1
fi

if [[ "$ROOT_DIR" == "$OCI_DEPLOY_PATH" ]]; then
  echo "ROOT_DIR e OCI_DEPLOY_PATH são iguais; nada para sincronizar." >&2
  exit 1
fi

mkdir -p "$OCI_DEPLOY_PATH"

cd "$ROOT_DIR"

rsync -az --delete \
  --exclude '/.git/' \
  --exclude '/.venv/' \
  --exclude '/.venv-oci/' \
  --exclude '/.venv-py39-backup/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '/.env' \
  --exclude '/.env.*' \
  --exclude '/logs/' \
  --exclude '/backups/' \
  --exclude '/reports/' \
  --exclude '/database/' \
  --exclude '/build/' \
  --exclude '/dist/' \
  ./ "$OCI_DEPLOY_PATH/"

cd "$OCI_DEPLOY_PATH"
test -f .env
mkdir -p /opt/girofy/backups

docker compose -f docker-compose.oci.yml up -d --build --remove-orphans
docker image prune -f >/dev/null

for attempt in {1..30}; do
  if curl -fsS "http://127.0.0.1:$OCI_DEPLOY_PORT/login" >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    curl -fsS "http://127.0.0.1:$OCI_DEPLOY_PORT/login" >/dev/null
    docker compose -f docker-compose.oci.yml logs --tail=120 app caddy
    exit 1
  fi
  sleep 3
done

docker compose -f docker-compose.oci.yml ps
echo "Deploy local concluído em http://127.0.0.1:$OCI_DEPLOY_PORT"

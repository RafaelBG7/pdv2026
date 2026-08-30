#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OCI_DEPLOY_HOST="${OCI_DEPLOY_HOST:-168.75.101.126}"
OCI_DEPLOY_USER="${OCI_DEPLOY_USER:-ubuntu}"
OCI_DEPLOY_PATH="${OCI_DEPLOY_PATH:-/opt/girofy/app}"
OCI_DEPLOY_PORT="${OCI_DEPLOY_PORT:-18080}"
DEPLOY_SHA="${DEPLOY_SHA:-${GITHUB_SHA:-unknown}}"
SSH_OPTS="${SSH_OPTS:- -o StrictHostKeyChecking=no }"

if [[ -z "$OCI_DEPLOY_HOST" || -z "$OCI_DEPLOY_USER" || -z "$OCI_DEPLOY_PATH" ]]; then
  echo "Configure OCI_DEPLOY_HOST, OCI_DEPLOY_USER e OCI_DEPLOY_PATH." >&2
  exit 1
fi

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
  -e "ssh $SSH_OPTS" \
  ./ "$OCI_DEPLOY_USER@$OCI_DEPLOY_HOST:$OCI_DEPLOY_PATH/"

ssh $SSH_OPTS "$OCI_DEPLOY_USER@$OCI_DEPLOY_HOST" bash -s <<REMOTE
set -euo pipefail
cd "$OCI_DEPLOY_PATH"
test -f .env
mkdir -p /opt/girofy/backups
export APP_VERSION="$DEPLOY_SHA"
echo "ENVIRONMENT=PRODUCTION"
echo "Gerando backup obrigatório antes das migrations."
docker compose -f docker-compose.oci.yml build app backup
docker compose -f docker-compose.oci.yml up -d mysql redis
backup_marker="\$(mktemp)"
docker compose -f docker-compose.oci.yml run --rm -e AUTO_BACKUP_ONCE=1 backup
latest_backup="\$(find /opt/girofy/backups -maxdepth 1 -type f -name 'girofy_mysql_full_*.sql' -newer "\$backup_marker" -print -quit)"
rm -f "\$backup_marker"
if [[ -z "\$latest_backup" || ! -s "\$latest_backup" ]]; then
  echo "Backup de produção não confirmado; migrations e limpeza canceladas." >&2
  exit 1
fi
echo "Aplicando migrations somente no MySQL de produção."
docker compose -f docker-compose.oci.yml run --rm --no-deps app python scripts/schema_migrate.py upgrade-all
echo "Removendo eventual tenant legado do Painel Master após backup validado."
docker compose -f docker-compose.oci.yml run --rm --no-deps app python scripts/cleanup_system_tenant.py --apply
docker compose -f docker-compose.oci.yml up -d --remove-orphans app backup caddy
docker image prune -f >/dev/null
for attempt in {1..30}; do
  if curl -fsS "http://127.0.0.1:$OCI_DEPLOY_PORT/login" >/dev/null 2>&1; then
    break
  fi
  if [[ "\$attempt" -eq 30 ]]; then
    curl -fsS "http://127.0.0.1:$OCI_DEPLOY_PORT/login" >/dev/null
    docker compose -f docker-compose.oci.yml logs --tail=120 app caddy
    exit 1
  fi
  sleep 3
done
docker compose -f docker-compose.oci.yml ps
curl -fsS "http://127.0.0.1:$OCI_DEPLOY_PORT/health/dependencies" >/dev/null
curl -fsS "http://127.0.0.1:$OCI_DEPLOY_PORT/api/v1/health/dependencies" >/dev/null
version_payload="\$(curl -fsS "http://127.0.0.1:$OCI_DEPLOY_PORT/health/version")"
if [[ "$DEPLOY_SHA" != unknown ]] && ! grep -Fq "$DEPLOY_SHA" <<<"\$version_payload"; then
  echo "O endpoint de versão PROD não confirmou o commit implantado." >&2
  exit 1
fi
printf '%s\n' "$DEPLOY_SHA" > DEPLOYED_COMMIT
REMOTE

echo "Deploy OCI concluído em http://$OCI_DEPLOY_HOST:$OCI_DEPLOY_PORT"

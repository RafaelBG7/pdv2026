#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HML_DEPLOY_PATH="${HML_DEPLOY_PATH:-/opt/girofy/hml}"
PRODUCTION_DEPLOY_PATH="${PRODUCTION_DEPLOY_PATH:-/opt/girofy/app}"
HML_LOOPBACK_PORT="${HML_LOOPBACK_PORT:-18081}"
DEPLOY_SHA="${DEPLOY_SHA:-${GITHUB_SHA:-unknown}}"
COMPOSE=(docker compose --env-file .env.hml -p skygest-hml -f docker-compose.hml.yml)

echo "ENVIRONMENT=HOMOLOGATION"
echo "DEPLOY_PATH=$HML_DEPLOY_PATH"
echo "DEPLOY_SHA=$DEPLOY_SHA"

if [[ "$HML_DEPLOY_PATH" == "$PRODUCTION_DEPLOY_PATH" || "$HML_DEPLOY_PATH" != /opt/girofy/hml ]]; then
  echo "Diretório HML recusado: deve ser /opt/girofy/hml e diferente de produção." >&2
  exit 1
fi

available_kb="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
available_disk_kb="$(df -Pk /opt/girofy | awk 'NR == 2 {print $4}')"
if (( available_kb < 220000 )); then
  echo "Memória disponível insuficiente para publicar HML com segurança (${available_kb} KiB)." >&2
  exit 1
fi
if (( available_disk_kb < 4194304 )); then
  echo "Espaço livre insuficiente para publicar HML com segurança." >&2
  exit 1
fi

mkdir -p "$HML_DEPLOY_PATH" "$HML_DEPLOY_PATH/backups"
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
  ./ "$HML_DEPLOY_PATH/"

export HML_DEPLOY_PATH
bash "$HML_DEPLOY_PATH/scripts/provision_hml_env.sh"
cd "$HML_DEPLOY_PATH"

python3 scripts/validate_environment_isolation.py \
  --environment homologation \
  --env-file .env.hml \
  --production-env-file "$PRODUCTION_DEPLOY_PATH/.env"

export APP_VERSION="$DEPLOY_SHA"
export HML_LOOPBACK_PORT
"${COMPOSE[@]}" config --quiet

existing_caddy_id="$("${COMPOSE[@]}" ps -q caddy 2>/dev/null || true)"
if ss -ltn | grep -Eq "127\\.0\\.0\\.1:${HML_LOOPBACK_PORT}[[:space:]]" && [[ -z "$existing_caddy_id" ]]; then
  echo "A porta loopback $HML_LOOPBACK_PORT já está ocupada por outro processo." >&2
  exit 1
fi

"${COMPOSE[@]}" build app backup
"${COMPOSE[@]}" up -d mysql redis

echo "Gerando backup HML obrigatório antes das migrations."
backup_marker="$(mktemp)"
"${COMPOSE[@]}" run --rm -e AUTO_BACKUP_ONCE=1 backup
latest_backup="$(find "$HML_DEPLOY_PATH/backups" -maxdepth 1 -type f -name 'girofy_mysql_full_*.sql' -newer "$backup_marker" -print -quit)"
rm -f "$backup_marker"
if [[ -z "$latest_backup" || ! -s "$latest_backup" ]]; then
  echo "Backup HML obrigatório não foi confirmado; migrations canceladas." >&2
  exit 1
fi

echo "Aplicando migrations somente no MySQL HML."
"${COMPOSE[@]}" run --rm --no-deps app python scripts/schema_migrate.py upgrade-all
"${COMPOSE[@]}" up -d --remove-orphans app backup caddy

for attempt in {1..40}; do
  if curl -fsS "http://127.0.0.1:${HML_LOOPBACK_PORT}/health/dependencies" >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 40 ]]; then
    "${COMPOSE[@]}" logs --tail=160 app caddy mysql redis
    exit 1
  fi
  sleep 3
done

curl -fsS "http://127.0.0.1:${HML_LOOPBACK_PORT}/login" >/dev/null
curl -fsS "http://127.0.0.1:${HML_LOOPBACK_PORT}/health/dependencies" >/dev/null
curl -fsS "http://127.0.0.1:${HML_LOOPBACK_PORT}/api/v1/health/dependencies" >/dev/null
version_payload="$(curl -fsS "http://127.0.0.1:${HML_LOOPBACK_PORT}/health/version")"
if [[ "$DEPLOY_SHA" != unknown ]] && ! grep -Fq "$DEPLOY_SHA" <<<"$version_payload"; then
  echo "O endpoint de versão HML não confirmou o commit implantado." >&2
  exit 1
fi

printf '%s\n' "$DEPLOY_SHA" > DEPLOYED_COMMIT
"${COMPOSE[@]}" ps
echo "HML interno saudável em http://127.0.0.1:${HML_LOOPBACK_PORT} no commit $DEPLOY_SHA."

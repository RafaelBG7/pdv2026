#!/usr/bin/env bash
set -euo pipefail

HML_DIR="${HML_DEPLOY_PATH:-/opt/girofy/hml}"
HML_ENV_FILE="$HML_DIR/.env.hml"

if [[ -f "$HML_ENV_FILE" ]]; then
  echo "Arquivo .env.hml existente preservado."
  exit 0
fi

if [[ ${#HML_MASTER_DEFAULT_PASSWORD} -lt 12 ]]; then
  echo "HML_MASTER_DEFAULT_PASSWORD deve possuir ao menos 12 caracteres no primeiro deploy." >&2
  exit 1
fi

umask 077
mkdir -p "$HML_DIR" "$HML_DIR/backups"

secret_key="$(openssl rand -hex 48)"
api_token_secret="$(openssl rand -hex 48)"
mysql_root_password="$(openssl rand -hex 32)"
mysql_password="$(openssl rand -hex 32)"

cat > "$HML_ENV_FILE" <<EOF
APP_ENV=homologation
FLASK_DEBUG=0
PUBLIC_BASE_URL=https://hml.skygest.com.br
SECRET_KEY=$secret_key
API_TOKEN_SECRET=$api_token_secret
MASTER_DEFAULT_USERNAME=master_hml
MASTER_DEFAULT_PASSWORD=$HML_MASTER_DEFAULT_PASSWORD
CSRF_ENABLED=1
SESSION_COOKIE_SECURE=1
SESSION_COOKIE_SAMESITE=Lax
API_ALLOW_INSECURE_AUTH=0
TRUST_PROXY_HEADERS=1
TRUSTED_PROXY_COUNT=2
SCHEMA_MANAGEMENT_MODE=verify
RATELIMIT_ENABLED=1
RATELIMIT_STORAGE_URI=redis://redis:6379/0
RATELIMIT_IN_MEMORY_FALLBACK_ENABLED=0
RATELIMIT_KEY_PREFIX=skygest-hml
MAIL_SUPPRESS_SEND=1
SUBSCRIPTION_COMMERCIAL_ENABLED=0
SUBSCRIPTION_WHATSAPP_NUMBER=
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=skygest_hml_central
MYSQL_USER=skygest_hml_app
MYSQL_PASSWORD=$mysql_password
MYSQL_ROOT_PASSWORD=$mysql_root_password
MYSQL_TENANT_DATABASE_PREFIX=skygest_hml_tenant
MYSQL_SERVER_DATABASE_URL=mysql+pymysql://root:$mysql_root_password@mysql:3306/mysql?charset=utf8mb4
HML_SITE_ADDRESS=:18081
HML_LOOPBACK_PORT=18081
HML_BACKUP_HOST_DIR=/opt/girofy/hml/backups
HML_BACKUP_UID=$(id -u)
HML_BACKUP_GID=$(id -g)
AUTO_BACKUP_ENABLED=1
AUTO_BACKUP_INTERVAL_SECONDS=86400
AUTO_BACKUP_RETENTION_DAYS=14
AUTO_BACKUP_RETENTION_COUNT=14
AUTO_AUDIT_CLEANUP_ENABLED=1
AUTO_AUDIT_CLEANUP_INTERVAL_SECONDS=259200
AUTO_AUDIT_RETENTION_DAYS=30
EOF

chmod 600 "$HML_ENV_FILE"
echo "Configuração HML criada com segredos exclusivos e permissões 600."

#!/usr/bin/env bash
set -euo pipefail

HML_DOMAIN="${HML_DOMAIN:-hml.skygest.com.br}"
EXPECTED_PUBLIC_IP="${EXPECTED_PUBLIC_IP:-168.75.101.126}"
HML_DEPLOY_PATH="${HML_DEPLOY_PATH:-/opt/girofy/hml}"
PRODUCTION_DEPLOY_PATH="${PRODUCTION_DEPLOY_PATH:-/opt/girofy/app}"
HML_LOOPBACK_PORT="${HML_LOOPBACK_PORT:-18081}"
NGINX_AVAILABLE="/etc/nginx/sites-available/skygest-hml"
NGINX_ENABLED="/etc/nginx/sites-enabled/skygest-hml"

echo "ENVIRONMENT=HOMOLOGATION"
if [[ "$HML_DOMAIN" != 'hml.skygest.com.br' ]]; then
  echo "Domínio HML recusado." >&2
  exit 1
fi
curl -fsS "http://127.0.0.1:${HML_LOOPBACK_PORT}/health/dependencies" >/dev/null

resolved_ips="$(getent ahostsv4 "$HML_DOMAIN" | awk '{print $1}' | sort -u || true)"
if ! grep -Fxq "$EXPECTED_PUBLIC_IP" <<<"$resolved_ips"; then
  echo "DNS pendente: crie o registro A hml -> $EXPECTED_PUBLIC_IP antes de configurar HTTPS." >&2
  exit 2
fi

echo "Gerando backup integral de produção antes de alterar o gateway compartilhado."
cd "$PRODUCTION_DEPLOY_PATH"
backup_marker="$(mktemp)"
docker compose -f docker-compose.oci.yml run --rm -e AUTO_BACKUP_ONCE=1 backup
production_backup="$(find /opt/girofy/backups -maxdepth 1 -type f -name 'girofy_mysql_full_*.sql' -newer "$backup_marker" -print -quit)"
rm -f "$backup_marker"
if [[ -z "$production_backup" || ! -s "$production_backup" ]]; then
  echo "Backup de produção não confirmado; gateway HML não será alterado." >&2
  exit 1
fi

timestamp="$(date -u '+%Y%m%d_%H%M%S')"
nginx_backup="/opt/girofy/backups/nginx_pre_hml_${timestamp}.tar.gz"
sudo -n tar -czf "$nginx_backup" /etc/nginx /etc/letsencrypt 2>/dev/null
sudo -n test -s "$nginx_backup"

had_existing=0
if sudo -n test -f "$NGINX_AVAILABLE"; then
  had_existing=1
  sudo -n cp "$NGINX_AVAILABLE" "${NGINX_AVAILABLE}.pre-${timestamp}"
fi

rollback_gateway() {
  if [[ "$had_existing" -eq 1 ]]; then
    sudo -n cp "${NGINX_AVAILABLE}.pre-${timestamp}" "$NGINX_AVAILABLE"
  else
    sudo -n rm -f "$NGINX_AVAILABLE" "$NGINX_ENABLED"
  fi
  sudo -n nginx -t && sudo -n systemctl reload nginx || true
}
trap rollback_gateway ERR

sudo -n install -m 644 "$HML_DEPLOY_PATH/deploy/nginx/skygest-hml.conf" "$NGINX_AVAILABLE"
sudo -n ln -sfn "$NGINX_AVAILABLE" "$NGINX_ENABLED"
sudo -n nginx -t
sudo -n systemctl reload nginx

if ! command -v certbot >/dev/null 2>&1; then
  echo "Certbot não está instalado; certificado HML não pode ser emitido." >&2
  exit 1
fi
sudo -n certbot --nginx --non-interactive --agree-tos --redirect --keep-until-expiring \
  --register-unsafely-without-email -d "$HML_DOMAIN"
sudo -n nginx -t
sudo -n systemctl reload nginx

curl -fsS "https://${HML_DOMAIN}/login" >/dev/null
curl -fsS "https://${HML_DOMAIN}/health/dependencies" >/dev/null
curl -fsS "https://${HML_DOMAIN}/api/v1/health/dependencies" >/dev/null
curl -fsS "https://skygest.com.br/health/dependencies" >/dev/null
echo | openssl s_client -connect "${HML_DOMAIN}:443" -servername "$HML_DOMAIN" 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates

trap - ERR
echo "Gateway HTTPS HML configurado e produção revalidada."

#!/usr/bin/env bash
set -euo pipefail

MARKETING_DOMAIN="${MARKETING_DOMAIN:-skygest.com.br}"
MARKETING_WWW_DOMAIN="${MARKETING_WWW_DOMAIN:-www.skygest.com.br}"
APP_DOMAIN="${APP_DOMAIN:-app.skygest.com.br}"
EXPECTED_PUBLIC_IP="${EXPECTED_PUBLIC_IP:-168.75.101.126}"
PRODUCTION_DEPLOY_PATH="${OCI_DEPLOY_PATH:-/opt/girofy/app}"
NGINX_AVAILABLE="/etc/nginx/sites-available/skygest-production"
NGINX_ENABLED="/etc/nginx/sites-enabled/skygest-production"

if [[ "$MARKETING_DOMAIN" != 'skygest.com.br' \
  || "$MARKETING_WWW_DOMAIN" != 'www.skygest.com.br' \
  || "$APP_DOMAIN" != 'app.skygest.com.br' ]]; then
  echo "Domínios de produção recusados." >&2
  exit 1
fi

for domain in "$MARKETING_DOMAIN" "$MARKETING_WWW_DOMAIN" "$APP_DOMAIN"; do
  resolved_ips="$(getent ahostsv4 "$domain" | awk '{print $1}' | sort -u || true)"
  if ! grep -Fxq "$EXPECTED_PUBLIC_IP" <<<"$resolved_ips"; then
    echo "DNS pendente: $domain deve apontar para $EXPECTED_PUBLIC_IP." >&2
    exit 2
  fi
done

curl -fsS 'http://127.0.0.1:5003/health/dependencies' >/dev/null
test -f "$PRODUCTION_DEPLOY_PATH/deploy/nginx/skygest-production.conf"

timestamp="$(date -u '+%Y%m%d_%H%M%S')"
gateway_backup="/opt/girofy/backups/nginx_pre_production_gateway_${timestamp}.tar.gz"
sudo -n tar -czf "$gateway_backup" /etc/nginx /etc/letsencrypt 2>/dev/null
sudo -n test -s "$gateway_backup"

mapfile -t previous_production_sites < <(
  sudo -n grep -El 'server_name[^;]*[[:space:]](skygest\.com\.br|www\.skygest\.com\.br|app\.skygest\.com\.br)([[:space:]]|;)' \
    /etc/nginx/sites-enabled/* 2>/dev/null \
    | grep -Fvx "$NGINX_ENABLED" \
    || true
)

rollback_gateway() {
  sudo -n tar -xzf "$gateway_backup" -C / 2>/dev/null || true
  sudo -n nginx -t && sudo -n systemctl reload nginx || true
}
trap rollback_gateway ERR

for enabled_site in "${previous_production_sites[@]}"; do
  sudo -n rm -f "$enabled_site"
done

sudo -n install -m 644 \
  "$PRODUCTION_DEPLOY_PATH/deploy/nginx/skygest-production.conf" \
  "$NGINX_AVAILABLE"
sudo -n ln -sfn "$NGINX_AVAILABLE" "$NGINX_ENABLED"
sudo -n nginx -t
sudo -n systemctl reload nginx

if ! command -v certbot >/dev/null 2>&1; then
  echo "Certbot não está instalado; certificado de produção não pode ser expandido." >&2
  exit 1
fi

sudo -n certbot --nginx --non-interactive --agree-tos --redirect --keep-until-expiring \
  --register-unsafely-without-email --expand --cert-name "$MARKETING_DOMAIN" \
  -d "$MARKETING_DOMAIN" -d "$MARKETING_WWW_DOMAIN" -d "$APP_DOMAIN"
sudo -n nginx -t
sudo -n systemctl reload nginx

homepage_headers="$(curl --retry 5 --retry-all-errors --retry-delay 2 -fsS -D - \
  -o /tmp/skygest-production-homepage.html "https://${MARKETING_WWW_DOMAIN}/")"
grep -Fq 'SkyGest | PDV e gestão' /tmp/skygest-production-homepage.html
if grep -Eqi '^location:[[:space:]].*/login' <<<"$homepage_headers"; then
  echo "Homepage de produção ainda redireciona para o login." >&2
  exit 1
fi

apex_location="$(curl -sS -o /dev/null -w '%{redirect_url}' "https://${MARKETING_DOMAIN}/")"
if [[ "$apex_location" != "https://${MARKETING_WWW_DOMAIN}/" ]]; then
  echo "Domínio raiz não redirecionou para a homepage canônica." >&2
  exit 1
fi

curl --retry 5 --retry-all-errors --retry-delay 2 -fsS \
  "https://${APP_DOMAIN}/login" >/dev/null
curl --retry 5 --retry-all-errors --retry-delay 2 -fsS \
  "https://${APP_DOMAIN}/health/dependencies" >/dev/null

rm -f /tmp/skygest-production-homepage.html
trap - ERR
echo "Gateway de produção separado entre homepage e aplicação."

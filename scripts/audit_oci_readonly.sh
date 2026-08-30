#!/usr/bin/env bash
set -euo pipefail

DEPLOY_PATH="${OCI_DEPLOY_PATH:-/opt/girofy/app}"
COMPOSE_FILE="${OCI_COMPOSE_FILE:-docker-compose.oci.yml}"

section() {
  printf '\n== %s ==\n' "$1"
}

safe_sudo() {
  if sudo -n true >/dev/null 2>&1; then
    sudo -n "$@"
  else
    "$@"
  fi
}

section "Host"
hostname
uname -srmo
uptime

section "Recursos"
free -h
df -h / /opt/girofy 2>/dev/null || df -h /
swapon --show || true
docker system df
docker stats --no-stream

section "Portas em escuta"
safe_sudo ss -lntp || ss -lnt || true

section "Firewall"
safe_sudo ufw status verbose || true

section "Diretórios persistentes"
find /opt/girofy -maxdepth 2 -type d -printf '%M %u:%g %p\n' 2>/dev/null | sort

section "Docker Compose"
cd "$DEPLOY_PATH"
test -f "$COMPOSE_FILE"
test -f .env
printf 'deploy_path=%s\n' "$DEPLOY_PATH"
printf 'compose_file=%s\n' "$COMPOSE_FILE"
docker compose -f "$COMPOSE_FILE" ls 2>/dev/null || docker compose ls
docker compose -f "$COMPOSE_FILE" config --services
printf '%s\n' '-- volumes declarados --'
docker compose -f "$COMPOSE_FILE" config --volumes
printf '%s\n' '-- networks declaradas --'
docker compose -f "$COMPOSE_FILE" config --networks
docker compose -f "$COMPOSE_FILE" ps

section "Containers sem variáveis sensíveis"
for container_id in $(docker compose -f "$COMPOSE_FILE" ps -q); do
  docker inspect --format \
    'name={{.Name}} image={{.Config.Image}} status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}} restart={{.HostConfig.RestartPolicy.Name}} privileged={{.HostConfig.Privileged}} ports={{json .HostConfig.PortBindings}} networks={{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}} mounts={{range .Mounts}}{{.Type}}:{{.Source}}->{{.Destination}} {{end}}' \
    "$container_id"
done

section "Networks e volumes Docker"
docker network ls
docker volume ls

section "Backups de produção"
find /opt/girofy/backups -maxdepth 1 -type f -name 'girofy_mysql_full_*.sql' \
  -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ %s %f\n' 2>/dev/null | sort -r | head -n 5 || true

section "Proxy público"
safe_sudo systemctl is-active nginx || true
safe_sudo nginx -T 2>/dev/null \
  | grep -E '^[[:space:]]*(listen|server_name|proxy_pass|ssl_certificate|ssl_certificate_key)' \
  | sed -E 's#(ssl_certificate_key)[[:space:]]+.*;#\1 [CAMINHO_OCULTADO];#' || true

section "Caddy do Compose"
sed -n '1,120p' deploy/Caddyfile

section "Runner"
systemctl list-units --type=service --all --no-pager \
  | grep -E 'actions\.runner|github.*runner' || true

section "Auditoria somente leitura concluída"

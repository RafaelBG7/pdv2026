# Runbook - Deploy dos ambientes SkyGest

## Identificação rápida

| Item | Produção | Homologação |
|---|---|---|
| URL | `https://skygest.com.br` | `https://hml.skygest.com.br` |
| Branch | `main` | `develop` |
| Diretório | `/opt/girofy/app` | `/opt/girofy/hml` |
| Compose | `docker-compose.oci.yml` | `docker-compose.hml.yml` |
| Project | `app` (nome legado) | `skygest-hml` |
| Porta proxy local | App `127.0.0.1:5003` / Caddy `18080` | Caddy `127.0.0.1:18081` |
| Backups | `/opt/girofy/backups` | `/opt/girofy/hml/backups` |

## Variáveis e segredos

Produção preserva `/opt/girofy/app/.env`. HML preserva `/opt/girofy/hml/.env.hml`. Ambos devem ter modo 600. Nunca copiar um para o outro e nunca usar `docker compose config` em logs públicos, pois a saída resolvida pode conter credenciais.

No primeiro deploy HML, o GitHub Environment `homologation` precisa do secret `HML_MASTER_DEFAULT_PASSWORD`. Os demais segredos HML são gerados na própria VM e não aparecem no log.

## Containers

Produção:

```bash
cd /opt/girofy/app
docker compose -f docker-compose.oci.yml ps
```

Homologação:

```bash
cd /opt/girofy/hml
docker compose --env-file .env.hml -p skygest-hml -f docker-compose.hml.yml ps
```

## Logs

```bash
# PROD
cd /opt/girofy/app
docker compose -f docker-compose.oci.yml logs --tail=200 app mysql redis caddy

# HML
cd /opt/girofy/hml
docker compose --env-file .env.hml -p skygest-hml -f docker-compose.hml.yml logs --tail=200 app mysql redis caddy
```

## Restart isolado

```bash
# PROD
cd /opt/girofy/app
docker compose -f docker-compose.oci.yml restart app

# HML
cd /opt/girofy/hml
docker compose --env-file .env.hml -p skygest-hml -f docker-compose.hml.yml restart app
```

## Health checks

```bash
curl -fsS https://skygest.com.br/health
curl -fsS https://skygest.com.br/health/dependencies
curl -fsS https://skygest.com.br/api/v1/health/dependencies
curl -fsS https://skygest.com.br/health/version

curl -fsS https://hml.skygest.com.br/health
curl -fsS https://hml.skygest.com.br/health/dependencies
curl -fsS https://hml.skygest.com.br/api/v1/health/dependencies
curl -fsS https://hml.skygest.com.br/health/version
```

## MySQL e Redis

```bash
# PROD
cd /opt/girofy/app
docker compose -f docker-compose.oci.yml exec mysql mysqladmin ping -h 127.0.0.1 -uroot -p
docker compose -f docker-compose.oci.yml exec redis redis-cli ping

# HML
cd /opt/girofy/hml
docker compose --env-file .env.hml -p skygest-hml -f docker-compose.hml.yml exec mysql mysqladmin ping -h 127.0.0.1 -uroot -p
docker compose --env-file .env.hml -p skygest-hml -f docker-compose.hml.yml exec redis redis-cli ping
```

O prompt de senha evita registrar credenciais no histórico do shell.

## Backup manual

```bash
# PROD
cd /opt/girofy/app
docker compose -f docker-compose.oci.yml run --rm -e AUTO_BACKUP_ONCE=1 backup

# HML
cd /opt/girofy/hml
docker compose --env-file .env.hml -p skygest-hml -f docker-compose.hml.yml run --rm -e AUTO_BACKUP_ONCE=1 backup
```

Confirme que o arquivo novo existe e possui tamanho maior que zero no diretório correto.

## Deploy e promoção

HML automático: push/merge para `develop`. PROD automático: push/merge para `main`. Para execução manual, use GitHub Actions e selecione o workflow correspondente. Não execute o workflow de produção para testar HML.

1. Merge da branch de trabalho em `develop`.
2. Aguardar deploy HML e todos os health checks.
3. Homologar em `https://hml.skygest.com.br`.
4. Abrir merge de `develop` para `main`.
5. Aprovar conscientemente a produção.
6. Revalidar login, dependências e versão PROD.

## DNS e HTTPS HML

```text
Tipo: A
Nome: hml
Destino: 168.75.101.126
TTL: padrão do provedor
```

Valide com `dig +short A hml.skygest.com.br`. Somente quando o DNS retornar `168.75.101.126`, `scripts/configure_hml_gateway.sh` instala o virtual host, emite certificado Let's Encrypt e valida HML e PROD. Antes, o script gera backup integral do MySQL PROD e backup de Nginx/Let's Encrypt.

Nenhuma porta nova precisa ser aberta na OCI ou no UFW: HML reutiliza 80/443 por hostname e 18081 fica em loopback.

## Identificar commit implantado

```bash
curl -fsS https://skygest.com.br/health/version
curl -fsS https://hml.skygest.com.br/health/version
cat /opt/girofy/app/DEPLOYED_COMMIT
cat /opt/girofy/hml/DEPLOYED_COMMIT
```

## Rollback HML

Crie um commit de reversão em `develop` ou publique uma branch baseada no commit anterior. Nunca reescreva histórico. Se houver incompatibilidade de schema, pare escritas e restaure somente um dump de `/opt/girofy/hml/backups`; não execute downgrade automático.

## Rollback PROD

Bloqueie novas escritas se necessário, preserve o backup pré-deploy, reverta o commit em `main` sem force push e restaure apenas o dump PROD correto sob procedimento controlado. Depois valide login, banco, Redis e versão.

Nunca usar `docker compose down -v`, `docker volume prune`, `DROP DATABASE` ou downgrade Alembic destrutivo.

## Auditoria somente leitura

No workflow `Deploy OCI Self Hosted`, escolha a operação `audit`. Ela mostra recursos, portas, firewall, containers, mounts, redes, volumes, backups e proxy sem imprimir `.env` ou executar deploy.

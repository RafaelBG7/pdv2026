# 34 - Ambientes de produção e homologação

## Objetivo e fluxo

O SkyGest mantém dois ambientes independentes:

```text
branch de trabalho -> develop -> HOMOLOGAÇÃO -> aprovação humana -> main -> PRODUÇÃO
```

Não existe promoção automática de HML para PROD. O merge em `main` é a aprovação explícita.

| Ambiente | URL | Branch | Diretório OCI | Compose project |
|---|---|---|---|---|
| Produção | `https://skygest.com.br` | `main` | `/opt/girofy/app` | `app` (legado preservado) |
| Homologação | `https://hml.skygest.com.br` | `develop` | `/opt/girofy/hml` | `skygest-hml` |

## Arquitetura real da OCI

A VM `girofy-app-01` possui 1 GiB de RAM e usa Nginx no host como gateway público em 80/443. Produção é encaminhada diretamente para o App em `127.0.0.1:5003`. O Caddy legado da stack PROD continua disponível na porta 18080 e não foi recriado.

Homologação usa uma stack própria com limites conservadores de memória:

```text
Internet
  -> Nginx compartilhado (host, seleção por hostname)
     -> skygest.com.br -> App PROD 127.0.0.1:5003
     -> hml.skygest.com.br -> Caddy HML 127.0.0.1:18081
        -> App HML -> MySQL HML + Redis HML
```

O gateway Nginx é compartilhado somente na borda. Dados, segredos, containers, rede, volumes, backups e logs não são compartilhados.

## Isolamento HML

- MySQL: container e volume `skygest_hml_mysql_data` exclusivos.
- Banco central: `skygest_hml_central`.
- Prefixo tenant: `skygest_hml_tenant`.
- Redis: container exclusivo, 32 MB, sem persistência e sem porta publicada.
- Network: `skygest_hml_internal`.
- Logs/reports: volumes `skygest_hml_logs` e `skygest_hml_reports`.
- Backups: bind mount `/opt/girofy/hml/backups`, retenção padrão de 14 dias/arquivos.
- `.env`: `/opt/girofy/hml/.env.hml`, modo 600, nunca versionado.
- E-mail: `MAIL_SUPPRESS_SEND=1`.
- Contratação/WhatsApp: `SUBSCRIPTION_COMMERCIAL_ENABLED=0`.
- Caddy HML: publicado somente em `127.0.0.1:18081`.
- MySQL, Redis e Gunicorn HML não possuem publicação de portas no host.
- O Painel Master é apenas o contexto administrativo do SaaS no banco central: não recebe `database_path`, não entra na lista de tenants e não possui schema próprio em nenhum ambiente.

## Segurança production-like

`APP_ENV=homologation` aplica as mesmas proteções obrigatórias de produção: debug desligado, cookies Secure, schema em `verify`, Redis obrigatório, fallback em memória recusado, HTTPS obrigatório para autenticação da API, CSRF e headers de segurança preservados.

Antes de migrations, `scripts/validate_environment_isolation.py` recusa domínio, banco, Redis, backup path ou segredos cruzados. `scripts/deploy_hml.sh` gera backup HML integral e aborta na primeira falha.

Após o backup validado, `scripts/cleanup_system_tenant.py` remove de forma idempotente apenas o schema legado cujo nome corresponde exatamente ao ID e ao nome do contexto `is_system`. A operação é recusada se o banco estiver compartilhado, tiver nome inesperado ou contiver referência de uma adega real.

## CI/CD

- `.github/workflows/deploy-hml-oci.yml`: push em `develop` ou execução manual; testes, migrations, Compose, guardrails, deploy HML, HTTPS e health checks.
- `.github/workflows/deploy-oci-self-hosted.yml`: push em `main` ou execução manual; produção apenas.
- Ambos usam o mesmo concurrency group para impedir builds simultâneos na VM de 1 GiB.
- GitHub Environments: `homologation` e `production`.

## Windows

O build normal usa `https://skygest.com.br` e recusa HTTP inseguro. Para homologação, iniciar com `SKYGEST_ENVIRONMENT=Homologation`; o arquivo `appsettings.Homologation.json` aponta para `https://hml.skygest.com.br`, também sem HTTP inseguro.

Os instaladores comerciais nunca devem definir `SKYGEST_ENVIRONMENT=Homologation`.

## Operação

O runbook completo, rollback e comandos sem segredos estão em [DEPLOY_AMBIENTES.md](DEPLOY_AMBIENTES.md).

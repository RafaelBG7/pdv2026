# 12 - Deploy

> O fluxo atual possui ambientes independentes. Consulte [Ambientes](34-separacao-producao-homologacao.md) e o [runbook operacional](DEPLOY_AMBIENTES.md). As referências históricas abaixo à porta 18080 descrevem o acesso legado de produção, não a homologação.

## Deploy com migrations

O deploy OCI executa `backup → migration central → migrations tenants → containers → health checks` e para na primeira falha. Procedimentos operacionais e restauração: [29-migracoes-versionadas.md](29-migracoes-versionadas.md).

## Status Atual

O Girofy já possui três formas principais de execução:

- local, para desenvolvimento e testes;
- desktop, para distribuição como app local;
- OCI Free Tier, para ambiente online usando Docker.

O ambiente OCI atual usa:

- VM `VM.Standard.E2.1.Micro`;
- Docker Compose;
- container da aplicação Flask;
- container MySQL;
- Caddy como proxy interno na porta pública alta `18080`;
- MySQL sem porta pública;
- SSH restrito ao IP administrativo;
- 80/443 fechadas até existir domínio/HTTPS.

## Execução Local

```bash
cd /Users/rafaelborges/pdv-adega-jf
source .venv/bin/activate
python app.py
```

Acesse:

```text
http://127.0.0.1:5003
```

Para trocar a porta:

```bash
PORT=5002 python app.py
```

O projeto carrega `.env` automaticamente ao iniciar. Variáveis exportadas no terminal também funcionam.

## MySQL Local

O MySQL precisa estar instalado e rodando para execução local.

Banco central padrão:

```text
adega_central
```

Criar manualmente, se necessário:

```sql
CREATE DATABASE adega_central CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Cada adega possui um banco operacional próprio, usando o prefixo configurado:

```text
adega_1_nome_da_adega
adega_2_outra_adega
```

## Variáveis de Ambiente

Modelo em `.env.example`:

```env
SECRET_KEY=troque-esta-chave-em-producao
APP_ENV=production
FLASK_DEBUG=0
MASTER_DEFAULT_USERNAME=master
MASTER_DEFAULT_PASSWORD=troque-esta-senha
PASSWORD_MIN_LENGTH=8
PASSWORD_MAX_LENGTH=128
CSRF_ENABLED=1
SESSION_LIFETIME_HOURS=8
SESSION_COOKIE_SECURE=1
SESSION_COOKIE_SAMESITE=Lax
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=adega_central
MYSQL_TENANT_DATABASE_PREFIX=adega
MYSQL_TENANT_DATABASE_URL_TEMPLATE=
MYSQL_SERVER_DATABASE_URL=mysql+pymysql://root@127.0.0.1:3306/mysql?charset=utf8mb4
PUBLIC_BASE_URL=http://127.0.0.1:5003
PORT=5003
```

Em produção, a aplicação recusa iniciar com `SECRET_KEY` padrão ou `MASTER_DEFAULT_PASSWORD=master123`. Para detalhes de segurança e validações, consulte `docs/security-hardening.md`.

## Deploy Manual na OCI

O deploy manual usa:

```text
scripts/deploy_oci_app.sh
```

Variáveis esperadas:

```env
OCI_DEPLOY_HOST=IP_PUBLICO_DA_VM
OCI_DEPLOY_USER=ubuntu
OCI_DEPLOY_PATH=/opt/girofy/app
OCI_DEPLOY_PORT=18080
```

Executar:

```bash
scripts/deploy_oci_app.sh
```

O script sincroniza o código, preserva o `.env` remoto, reconstrói os containers e valida `/login`.

Antes do deploy manual por SSH, a security list da OCI precisa liberar o IP público
atual do operador na porta 22. O script de rede usado para isso é:

```bash
scripts/oci/oci_harden_network.sh
```

Variável usada:

```env
OCI_ALLOWED_SSH_CIDR=SEU_IP_PUBLICO/32
```

Depois da publicação, valide:

```bash
curl -I http://IP_PUBLICO_DA_VM:18080/login
```

## Pipeline GitHub Actions Recomendada

Workflow:

```text
.github/workflows/deploy-oci-self-hosted.yml
```

Ele executa:

- testes automatizados;
- validação dos scripts de infraestrutura;
- deploy dentro da própria VM OCI usando self-hosted runner;
- rebuild dos containers;
- health check local em `/login`.

Esse fluxo não depende de SSH externo, IP público do desenvolvedor nem sessão OCI CLI. A instalação do runner é feita uma vez na VM com:

```text
scripts/oci/install_github_runner.sh
```

Variáveis opcionais no ambiente `production`:

```text
OCI_DEPLOY_PATH=/opt/girofy/app
OCI_DEPLOY_PORT=18080
```

Execução manual:

```text
GitHub > Actions > Deploy OCI Self Hosted > Run workflow
```

Execução automática:

- push para `main`;
- alterações somente em `docs/**` ou `*.md` não disparam deploy.

## Pipeline SSH De Emergência

Workflow:

```text
.github/workflows/deploy-oci.yml
```

Esse fluxo é manual e usa `scripts/deploy_oci_app.sh` com SSH/rsync. Ele permanece como fallback, mas depende de `OCI_SSH_PRIVATE_KEY` e regras de rede liberando SSH.

## Acesso dos Clientes

O canal oficial é a aplicação web hospedada na OCI:

```text
https://skygest.com.br
```

O computador do cliente precisa somente de um navegador e acesso à internet. MySQL,
Flask, arquivos `.env`, backups e segredos permanecem exclusivamente no servidor.

O projeto `desktop_wpf/` é o cliente nativo Windows 0.9.2-preview. Ele consome a API
HTTPS implantada, mas possui workflow de build/release próprio e não faz parte do
container Web.

## Checklist de Produção

Itens já aplicados no ambiente OCI atual:

- `DEBUG=False`;
- app e banco em Docker;
- MySQL sem exposição pública;
- SSH sem senha;
- SSH root desativado;
- SSH restrito ao IP administrativo;
- fail2ban para SSH;
- UFW ativo;
- porta pública alta `18080`;
- 80/443 fechadas enquanto não houver domínio.
- deploy manual validado via `scripts/deploy_oci_app.sh` com rebuild dos containers e health check em `/login`.

Itens ainda recomendados:

- domínio definitivo;
- HTTPS com Caddy;
- monitoramento do Redis usado pelo rate limit persistente;
- Alembic/Flask-Migrate;
- auditoria de ações de negócio;
- backup externo fora da VM;
- restauração guiada de backup;
- política real de cobrança Basic/Pro;
- HTTPS antes de expor autenticação por API para clientes nativos.

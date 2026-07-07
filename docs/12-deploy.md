# 12 - Deploy

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

## Pipeline GitHub Actions

Workflow:

```text
.github/workflows/deploy-oci.yml
```

Ele executa:

- testes automatizados;
- validação dos scripts de infraestrutura;
- deploy via SSH/rsync;
- rebuild dos containers;
- health check público.

Secrets obrigatórios no GitHub:

```text
OCI_DEPLOY_HOST
OCI_DEPLOY_USER
OCI_DEPLOY_PATH
OCI_SSH_PRIVATE_KEY
```

Variável opcional no ambiente `production`:

```text
OCI_DEPLOY_PORT=18080
```

Execução manual:

```text
GitHub > Actions > Deploy OCI > Run workflow
```

Execução automática:

- push para `main`;
- alterações somente em `docs/**` ou `*.md` não disparam deploy.

## Desktop

Builds desktop são gerados pelo workflow:

```text
.github/workflows/build-desktop.yml
```

Artefatos:

- `Girofy-macOS.zip`;
- `Girofy-Windows.zip`;
- `Girofy-Setup.exe`.

Para reduzir bloqueios do Windows SmartScreen e Apple Gatekeeper, configure certificados de assinatura nos secrets do GitHub. Sem assinatura reconhecida, o sistema operacional pode avisar que o app não é confiável.

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

Itens ainda recomendados:

- domínio definitivo;
- HTTPS com Caddy;
- CSRF nos formulários;
- Alembic/Flask-Migrate;
- auditoria de ações de negócio;
- backup externo fora da VM;
- restauração guiada de backup;
- política real de cobrança Basic/Pro;
- assinatura digital dos instaladores desktop.

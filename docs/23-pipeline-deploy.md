# 23 - Pipeline de Deploy

## Objetivo

Automatizar o deploy do Girofy para a VM OCI sem enviar arquivos sensíveis do ambiente local.

Workflow recomendado:

```text
.github/workflows/deploy-oci-self-hosted.yml
```

Esse workflow roda o deploy dentro da própria VM OCI usando um GitHub Actions self-hosted runner. Assim o deploy não depende do IP público do desenvolvedor, não precisa abrir SSH para runners externos do GitHub e não exige sessão ativa da OCI CLI.

Workflow de emergência por SSH:

```text
.github/workflows/deploy-oci.yml
```

Script chamado pela pipeline recomendada:

```text
scripts/deploy_self_hosted_app.sh
```

Script chamado pela pipeline SSH de emergência:

```text
scripts/deploy_oci_app.sh
```

## Quando Roda

Manual:

```text
GitHub > Actions > Deploy OCI Self Hosted > Run workflow
```

Automático:

- push para a branch `main`;
- alterações apenas em `docs/**` ou `*.md` não disparam deploy.

## Instalação Única Do Runner Na VM

No GitHub, gere o token do runner em:

```text
Settings > Actions > Runners > New self-hosted runner > Linux
```

Na VM OCI, execute:

```bash
cd /opt/girofy/app
GITHUB_REPOSITORY_URL=https://github.com/SEU_USUARIO/SEU_REPOSITORIO \
GITHUB_RUNNER_TOKEN=TOKEN_GERADO_PELO_GITHUB \
scripts/oci/install_github_runner.sh
```

O runner é instalado como serviço em:

```text
/opt/actions-runner-girofy
```

Labels usadas pela pipeline:

```text
self-hosted
linux
girofy-oci
```

Depois disso, o deploy padrão não precisa mais de acesso SSH externo.

## Secrets Necessários Para O Fluxo Recomendado

Nenhum secret é necessário para o deploy self-hosted, porque ele roda dentro da VM e preserva o `.env` que já existe em `/opt/girofy/app/.env`.

Variáveis opcionais no ambiente `production`:

```text
OCI_DEPLOY_PATH=/opt/girofy/app
OCI_DEPLOY_PORT=18080
```

## Secrets Necessários Para Fallback SSH

No GitHub, configure em:

```text
Settings > Secrets and variables > Actions > Environment secrets > production
```

Secrets:

```text
OCI_DEPLOY_HOST=IP_PUBLICO_DA_VM
OCI_DEPLOY_USER=ubuntu
OCI_DEPLOY_PATH=/opt/girofy/app
OCI_SSH_PRIVATE_KEY=CHAVE_PRIVADA_SSH
```

Variável opcional:

```text
OCI_DEPLOY_PORT=18080
```

## O Que A Pipeline Recomendada Faz

1. Baixa o código do repositório.
2. Instala Python 3.13.
3. Instala as dependências do `requirements.txt`.
4. Executa `python -m unittest discover`.
5. Valida a sintaxe dos scripts de deploy.
6. Executa o job `deploy` no runner self-hosted da VM OCI.
7. Sincroniza o projeto para `/opt/girofy/app`.
8. Rebuilda os containers Docker.
9. Remove imagens antigas sem uso.
10. Valida `/login` dentro da VM.

## Arquivos Que Não Sobem

O script exclui:

- `.env`;
- `.env.*`;
- `.git`;
- `.venv`;
- `.venv-oci`;
- `logs`;
- `backups`;
- `reports`;
- `database`;
- `build`;
- `dist`;
- caches Python.

O `.env` real da VM deve permanecer em:

```text
/opt/girofy/app/.env
```

## Teste Manual Do Deploy Recomendado

Na VM OCI:

```bash
cd /opt/girofy/app
scripts/deploy_self_hosted_app.sh
```

## Teste Manual Do Deploy SSH

Na máquina local:

```bash
OCI_DEPLOY_HOST=IP_PUBLICO_DA_VM OCI_DEPLOY_USER=ubuntu OCI_DEPLOY_PATH=/opt/girofy/app OCI_DEPLOY_PORT=18080 scripts/deploy_oci_app.sh
```

Se concluir corretamente, a saída termina com:

```text
Deploy OCI concluído em http://IP_PUBLICO_DA_VM:18080
```

## Validação Depois Do Deploy

Checar login:

```bash
curl -I http://IP_PUBLICO_DA_VM:18080/login
```

Checar containers:

```bash
ssh ubuntu@IP_PUBLICO_DA_VM
cd /opt/girofy/app
docker compose -f docker-compose.oci.yml ps
```

## Cuidados

- Não coloque `.env` real no GitHub.
- Não coloque chave SSH diretamente no código.
- O runner self-hosted deve rodar com um usuário que consiga executar Docker.
- O `.env` real deve continuar apenas na VM.
- O health check espera o `/login` responder até 90 segundos após o rebuild.
- Se o token/session da OCI expirar, isso não afeta o deploy self-hosted; afeta apenas scripts que criam ou alteram recursos OCI.
- A pipeline SSH antiga continua disponível para emergência, mas depende de chave SSH e regras de rede.

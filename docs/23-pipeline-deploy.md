# 23 - Pipeline de Deploy

## Objetivo

Automatizar o deploy do Girofy para a VM OCI sem enviar arquivos sensíveis do ambiente local.

Workflow:

```text
.github/workflows/deploy-oci.yml
```

Script chamado pela pipeline:

```text
scripts/deploy_oci_app.sh
```

## Quando Roda

Manual:

```text
GitHub > Actions > Deploy OCI > Run workflow
```

Automático:

- push para a branch `main`;
- alterações apenas em `docs/**` ou `*.md` não disparam deploy.

## Secrets Necessários

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

## O Que A Pipeline Faz

1. Baixa o código do repositório.
2. Instala Python 3.13.
3. Instala as dependências do `requirements.txt`.
4. Executa `python -m unittest discover`.
5. Valida a sintaxe dos scripts de OCI/deploy.
6. Instala `rsync`.
7. Configura SSH temporário no runner.
8. Sincroniza o projeto para a VM.
9. Rebuilda os containers Docker.
10. Remove imagens antigas sem uso.
11. Valida `/login` dentro da VM.
12. Valida `/login` pela porta pública.

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

## Teste Manual Do Mesmo Deploy

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
- A chave `OCI_SSH_PRIVATE_KEY` deve ter acesso ao usuário remoto configurado.
- O usuário remoto precisa conseguir rodar Docker.
- O health check espera o `/login` responder até 90 segundos após o rebuild.
- Se o token/session da OCI expirar, isso não afeta o deploy por SSH; afeta apenas scripts que criam ou alteram recursos OCI.

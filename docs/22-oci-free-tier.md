# 22 - OCI Free Tier

## Objetivo

Preparar a hospedagem do Girofy na Oracle Cloud Infrastructure usando apenas recursos candidatos ao Always Free.

O desenho evita banco gerenciado e load balancer pago:

- 1 VM Compute Always Free;
- 50 GB de boot volume;
- VCN, subnet pública, internet gateway, route table e security list;
- Docker na VM;
- MySQL local em container;
- aplicação Flask em container;
- Caddy como proxy;
- porta pública alta `18080` enquanto não houver domínio/HTTPS.

## Status do Ambiente Atual

Em 05/07/2026, a região disponível na conta não tinha capacidade para `VM.Standard.A1.Flex`. O ambiente foi criado com fallback para:

```text
VM.Standard.E2.1.Micro
```

Configuração aplicada:

- aplicação pública em `http://IP_PUBLICO:18080`;
- 80/443 fechadas;
- SSH liberado apenas para o IP administrativo;
- MySQL sem exposição pública;
- Docker Compose rodando `app`, `mysql` e `caddy`;
- UFW ativo;
- fail2ban ativo;
- login SSH por senha desativado;
- login SSH root desativado;
- swap configurado para aliviar a RAM pequena da E2 Micro.

Se no futuro houver capacidade A1 disponível, o mesmo desenho pode ser recriado com mais memória.

## Por Que Esse Desenho

Para reduzir risco de cobrança, o primeiro ambiente usa uma única VM pequena. O MySQL roda localmente na própria VM via Docker, sem HeatWave/MySQL gerenciado.

Quando o produto amadurecer, dá para separar banco, backup externo, monitoramento e alta disponibilidade. Para agora, a prioridade é gastar zero e validar o SaaS online.

## Arquivos Criados

- `.env.oci.example`: modelo das credenciais OCI.
- `.venv-oci/`: ambiente local isolado onde a OCI CLI pode ser instalada.
- `scripts/oci/oci_session_login.sh`: cria login temporário por session token.
- `scripts/oci/oci_check.sh`: valida OCI CLI, chave e autenticação.
- `scripts/oci/oci_create_free_tier_vm.sh`: cria rede e VM por OCI CLI.
- `scripts/oci/cloud-init-girofy.yaml`: instala Docker e prepara `/opt/girofy`.
- `Dockerfile`: imagem da aplicação.
- `docker-compose.oci.yml`: aplicação, MySQL e Caddy.
- `deploy/Caddyfile`: proxy reverso.

## Variáveis OCI

Preencha no `.env` ou copie `.env.oci.example` para `.env.oci`.

```env
OCI_AUTH_MODE=security_token
OCI_CLI_PROFILE=GIROFY
OCI_CONFIG_FILE=/Users/rafaelborges/.oci/config
OCI_SESSION_EXPIRATION_MINUTES=60
OCI_BIN=/Users/rafaelborges/pdv-adega-jf/.venv-oci/bin/oci
OCI_CLI_TENANCY=
OCI_CLI_USER=
OCI_CLI_FINGERPRINT=
OCI_CLI_KEY_FILE=/Users/rafaelborges/.oci/oci_api_key.pem
OCI_CLI_REGION=sa-saopaulo-1
OCI_COMPARTMENT_ID=
OCI_AVAILABILITY_DOMAIN=
OCI_SSH_PUBLIC_KEY_FILE=/Users/rafaelborges/.ssh/id_ed25519.pub
OCI_ALLOWED_SSH_CIDR=SEU_IP_PUBLICO/32
OCI_ALLOWED_HTTP_CIDR=0.0.0.0/0
OCI_SHAPE=VM.Standard.A1.Flex
OCI_OCPUS=1
OCI_MEMORY_GB=6
OCI_BOOT_VOLUME_GB=50
OCI_PUBLIC_HTTP_PORT=18080
GIROFY_SITE_ADDRESS=:18080
GIROFY_PUBLIC_HTTP_PORT=18080
```

Para a E2 Micro usada no fallback:

```env
OCI_SHAPE=VM.Standard.E2.1.Micro
OCI_OCPUS=1
OCI_MEMORY_GB=1
```

## Instalar OCI CLI Local

A instalação recomendada para este projeto fica isolada em `.venv-oci/`, sem mexer no venv principal da aplicação:

```bash
rtk python3 -m venv .venv-oci
rtk .venv-oci/bin/python -m pip install --upgrade pip setuptools wheel
rtk .venv-oci/bin/python -m pip install oci-cli
rtk .venv-oci/bin/oci --version
```

## Login Com Session Token

Para não depender de API key agora, use sessão temporária:

```bash
rtk scripts/oci/oci_session_login.sh
```

Esse comando abre o login da Oracle Cloud no navegador. Depois de concluir o login, ele salva o perfil local `GIROFY` em `~/.oci/config` e o token em `~/.oci/sessions`.

Com session token, estas variáveis ficam ativas:

```env
OCI_AUTH_MODE=security_token
OCI_CLI_PROFILE=GIROFY
OCI_CONFIG_FILE=/Users/rafaelborges/.oci/config
```

O token expira. Quando expirar, rode novamente:

```bash
rtk scripts/oci/oci_session_login.sh
```

## Onde Encontrar Cada Campo

`OCI_AUTH_MODE`:
Use `security_token` para login temporário pelo navegador. Use `api_key` apenas quando quiser autenticação permanente por chave.

`OCI_CLI_PROFILE`:
Nome do perfil local salvo pela OCI CLI. O projeto usa `GIROFY`.

`OCI_CONFIG_FILE`:
Caminho do arquivo de configuração da OCI CLI. Para session token, normalmente é `~/.oci/config`.

`OCI_BIN`:
Caminho do executável local da OCI CLI. Neste projeto: `.venv-oci/bin/oci`.

`OCI_CLI_TENANCY`:
Tenancy OCID da sua conta OCI. Obrigatório no modo API key. No modo session token, não precisa para autenticar, mas ainda pode ser mantido como referência.

`OCI_CLI_USER`:
User OCID do usuário que terá a API key. Obrigatório apenas no modo API key.

`OCI_CLI_FINGERPRINT`:
Fingerprint da API key cadastrada no usuário. Obrigatório apenas no modo API key.

`OCI_CLI_KEY_FILE`:
Caminho local da private key correspondente à API key cadastrada na OCI. Obrigatório apenas no modo API key.

`OCI_CLI_REGION`:
Região da conta, por exemplo `sa-saopaulo-1`.

`OCI_COMPARTMENT_ID`:
OCID do compartment onde os recursos serão criados.

`OCI_AVAILABILITY_DOMAIN`:
Availability Domain da sua tenancy. Pode ser listado com:

```bash
rtk scripts/oci/oci_check.sh
rtk oci iam availability-domain list --compartment-id "$OCI_COMPARTMENT_ID"
```

`OCI_ALLOWED_SSH_CIDR`:
Seu IP público com `/32`. Evite deixar `0.0.0.0/0` para SSH.

## Validar Acesso

```bash
rtk scripts/oci/oci_session_login.sh
rtk scripts/oci/oci_check.sh
```

Se estiver tudo certo, o script mostra:

```text
Autenticação OCI OK.
```

## Criar Ambiente Free Tier

```bash
rtk scripts/oci/oci_create_free_tier_vm.sh
```

O script cria:

- VCN;
- internet gateway;
- route table;
- security list;
- subnet pública;
- VM;
- Docker via cloud-init.

No final ele mostra o IP público.

## Rede Segura Para Teste

Enquanto o Girofy estiver sem domínio público definitivo, use porta alta para o acesso público e mantenha apenas o SSH restrito ao seu IP:

```env
OCI_ALLOWED_SSH_CIDR=SEU_IP_PUBLICO/32
OCI_ALLOWED_HTTP_CIDR=0.0.0.0/0
OCI_PUBLIC_HTTP_PORT=18080
GIROFY_SITE_ADDRESS=:18080
GIROFY_PUBLIC_HTTP_PORT=18080
PUBLIC_BASE_URL=http://IP_PUBLICO:18080
```

Aplicar a Security List:

```bash
rtk scripts/oci/oci_harden_network.sh
```

Na VM, mantenha o UFW com SSH restrito e Girofy público na porta alta:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from SEU_IP_PUBLICO to any port 22 proto tcp
sudo ufw allow proto tcp from 0.0.0.0/0 to any port 18080
sudo ufw --force enable
```

Também foi aplicado no servidor:

- login SSH por senha desativado;
- login SSH root desativado;
- máximo de 3 tentativas por conexão SSH;
- fail2ban ativo para SSH;
- MySQL sem porta pública exposta;
- app Flask exposto apenas internamente para o Caddy.

Se seu IP público mudar, atualize `OCI_ALLOWED_SSH_CIDR` e rode novamente `rtk scripts/oci/oci_harden_network.sh`. O acesso web continua público quando `OCI_ALLOWED_HTTP_CIDR=0.0.0.0/0`.

## Subir o Girofy Na VM

Depois que a VM estiver criada:

```bash
ssh ubuntu@IP_PUBLICO
```

Envie o projeto para:

```text
/opt/girofy/app
```

Dentro da VM:

```bash
cd /opt/girofy/app
cp .env.example .env
```

Configure no `.env` da VM:

```env
APP_ENV=production
FLASK_DEBUG=0
SECRET_KEY=uma-chave-forte
MASTER_DEFAULT_PASSWORD=uma-senha-forte
MYSQL_ROOT_PASSWORD=uma-senha-root-forte
MYSQL_USER=girofy_app
MYSQL_PASSWORD=uma-senha-forte-do-app
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=adega_central
MYSQL_TENANT_DATABASE_PREFIX=adega
PORT=5003
GIROFY_SITE_ADDRESS=:18080
GIROFY_PUBLIC_HTTP_PORT=18080
PUBLIC_BASE_URL=http://IP_PUBLICO:18080
```

Suba:

```bash
docker compose -f docker-compose.oci.yml up -d --build
```

## Domínio

Sem domínio:

```env
GIROFY_SITE_ADDRESS=:18080
```

Com domínio apontado para o IP da VM:

```env
GIROFY_SITE_ADDRESS=girofy.seudominio.com.br
```

Nesse caso o Caddy tenta emitir HTTPS automaticamente.

## Deploy Por Pipeline

O deploy automatizado fica em:

```text
.github/workflows/deploy-oci.yml
```

Secrets necessários:

```text
OCI_DEPLOY_HOST
OCI_DEPLOY_USER
OCI_DEPLOY_PATH
OCI_SSH_PRIVATE_KEY
```

Variável recomendada:

```text
OCI_DEPLOY_PORT=18080
```

O workflow executa testes, envia o código para `/opt/girofy/app`, reconstrói os containers e valida `/login`.

Também é possível rodar o mesmo processo localmente:

```bash
OCI_DEPLOY_HOST=IP_PUBLICO OCI_DEPLOY_USER=ubuntu OCI_DEPLOY_PATH=/opt/girofy/app OCI_DEPLOY_PORT=18080 scripts/deploy_oci_app.sh
```

## Cuidados Para Não Sair Do Free Tier

- Não criar Load Balancer por enquanto.
- Não criar banco gerenciado por enquanto.
- Não aumentar `OCI_BOOT_VOLUME_GB` acima do planejado.
- Não criar múltiplas VMs sem conferir os limites Always Free atuais.
- Manter SSH restrito ao seu IP.
- Manter 80/443 fechadas no modo de teste sem domínio.
- Conferir no painel da OCI se todos os recursos aparecem como Always Free/candidatos ao Free Tier.

## Fontes Oficiais

- Oracle Free Tier: https://www.oracle.com/cloud/free/
- Always Free Resources: https://docs.oracle.com/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- OCI Free Tier: https://docs.oracle.com/iaas/Content/FreeTier/freetier.htm
- OCI CLI config: https://docs.oracle.com/iaas/Content/API/Concepts/sdkconfig.htm
- OCI CLI environment variables: https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/clienvironmentvariables.htm

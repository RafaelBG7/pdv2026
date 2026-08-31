# SkyGest

SkyGest é um SaaS de ponto de venda e gestão operacional para adegas e pequenos comércios. O repositório reúne backend Flask, interface Web, API REST, aplicativo Windows WPF, Painel Master e infraestrutura OCI para produção e homologação.

> A fonte técnica oficial é [DOCUMENTACAO_COMPLETA.md](DOCUMENTACAO_COMPLETA.md). Os documentos numerados em `docs/` aprofundam temas ou preservam marcos históricos.

## Estado atual

- Web/API em produção: [https://skygest.com.br](https://skygest.com.br)
- Homologação isolada: [https://hml.skygest.com.br](https://hml.skygest.com.br)
- App Windows: `0.9.2-preview`, .NET 8/WPF, online e sem banco local operacional
- Banco: MySQL central mais um banco físico por adega
- Painel Master: contexto administrativo central; não é adega e não possui banco tenant
- Planos comerciais: Basic, Pro e Ultimate; contratação temporariamente direcionada ao WhatsApp
- Cobertura automatizada inventariada: 251 testes backend e 153 casos xUnit WPF

## Funcionalidades

- cadastro por usuário, e-mail e senha, confirmação de e-mail e recuperação de acesso;
- produtos, categorias, kits, código de barras, importação e exportação;
- estoque e histórico de movimentos;
- PDV com dinheiro, Pix, débito, crédito e pagamentos mistos;
- caixa, cancelamento auditado, contas a pagar e relatórios;
- dashboard responsivo com períodos, comparativos, gráficos e tooltips;
- equipe, permissões, configurações, notificações e auditoria;
- gestão SaaS de adegas, usuários, assinaturas e keys no Painel Master;
- API REST v1 e cliente Windows com access/refresh token protegido por DPAPI;
- migrations central/tenant, backup pré-deploy, Redis e health checks.

Não existem hoje módulos funcionais de clientes, fornecedores, emissão fiscal, cobrança automática ou integração com adquirentes. Os planos ainda não aplicam cotas técnicas por recurso.

## Arquitetura resumida

```text
Web/Jinja ── cookie + CSRF ─┐
                            ├─ HTTPS ─ Flask/Gunicorn ─┬─ MySQL central
Windows WPF ─ Bearer/refresh┘                          ├─ MySQL por adega
                                                      ├─ Redis/rate limit
Painel Master ─ sessão Web ────────────────────────────└─ SMTP
```

O backend é a fonte de verdade para autenticação, autorização, cálculos, estoque, assinatura e isolamento de tenant. O App nunca acessa o MySQL diretamente.

## Estrutura

```text
app/                    Flask, Web, API, modelos e serviços
desktop_wpf/            solução .NET 8, WPF, xUnit e instalador
migrations/central/     schema central, head central_0009
migrations/tenant/      schema das adegas, head tenant_0009
scripts/                migrations, backup, deploy e OCI
deploy/                 Caddy e inicialização do MySQL
tests/                  contratos e integração do backend
docs/                   documentação temática e histórica
docker-compose.oci.yml  produção
docker-compose.hml.yml  homologação
```

## Desenvolvimento local

Pré-requisitos: Python 3.13 e MySQL 8 compatível. Redis é necessário para reproduzir o modo de produção.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# configure somente valores locais e nunca versione segredos
python scripts/schema_migrate.py upgrade-all
python app.py
```

Por padrão, a aplicação local usa a porta configurada em `PORT`. Produção rejeita secrets/defaults inseguros e schemas fora do head esperado.

### Testes backend

```bash
TESTING=1 MAIL_SUPPRESS_SEND=1 python -m unittest discover
```

### App Windows

Em Windows com SDK .NET 8:

```powershell
dotnet restore desktop_wpf/Girofy.Desktop.sln
dotnet test desktop_wpf/tests/Girofy.UnitTests/Girofy.UnitTests.csproj -c Release
dotnet run --project desktop_wpf/src/Girofy.Desktop/Girofy.Desktop.csproj
```

`appsettings.json` usa produção e `appsettings.Homologation.json` usa homologação, ambos com HTTPS obrigatório. O ambiente também pode ser selecionado por `SKYGEST_ENVIRONMENT`; sobrescritas `GIROFY_*` existem por compatibilidade interna.

## Produção e homologação

Os ambientes possuem bancos centrais, prefixos tenant, volumes, Redis, secrets, backups, projetos Compose e URLs independentes:

| Ambiente | Branch | Workflow | Banco central |
|---|---|---|---|
| Homologação | `develop` | `deploy-hml-oci.yml` | `skygest_hml_central` |
| Produção | `main` | `deploy-oci-self-hosted.yml` | `adega_central` |

O fluxo seguro é desenvolver → testar → publicar em `develop` → homologar → promover para `main`. Cada deploy executa testes, backup, migrations e health checks. Markdown isolado não dispara produção.

Runbooks:

- [Separação produção/homologação](docs/34-separacao-producao-homologacao.md)
- [Deploy dos ambientes](docs/DEPLOY_AMBIENTES.md)
- [Migrations central e tenant](docs/29-migracoes-versionadas.md)

## Segurança

O código implementa scrypt, CSRF e verificação de origem, cookie seguro, CSP/headers, HTTPS no App, access token curto, refresh com hash/rotação/revogação, rate limit Redis, isolamento físico por tenant, idempotência de venda, auditoria mascarada e backup antes de migration.

Segredos reais, `.env`, dumps, tokens, chaves SSH/OCI, logs, builds e relatórios não devem ser versionados. Pendências e riscos atuais estão na seção de segurança e dívida técnica da documentação oficial.

## Documentação

- [Documentação técnica completa](DOCUMENTACAO_COMPLETA.md)
- [Índice oficial](docs/00-INDEX.md)
- [Matriz Web/App/Backend](docs/MATRIX.md)
- [Paridade funcional](docs/FEATURE_PARITY.md)
- [Arquitetura](docs/03-arquitetura.md)
- [API](docs/09-api.md)
- [Segurança](docs/14-seguranca.md)
- [Testes](docs/15-testes.md)
- [Temas e acessibilidade](docs/shared/THEMING.md)

Em caso de divergência, prevalecem o código, as migrations versionadas e [DOCUMENTACAO_COMPLETA.md](DOCUMENTACAO_COMPLETA.md).

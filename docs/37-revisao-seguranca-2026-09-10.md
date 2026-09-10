# Revisão de segurança — 2026-09-10

Escopo: aplicação Flask/Jinja, API v1, autenticação, autorização, isolamento tenant,
imports, configuração, Docker, proxy, migrations e testes. A revisão foi executada
somente sobre desenvolvimento/homologação; produção não foi alterada.

## Já implementado e seguro

- senhas armazenadas com `scrypt`, política de tamanho e bloqueio de senhas comuns;
- login e recuperação sem enumeração de contas, inclusive com hash fictício no login da API;
- cookies `Secure`, `HttpOnly`, `SameSite=Lax` em ambientes protegidos e sessão de oito horas;
- CSRF global em POST/PUT/PATCH/DELETE da Web; API usa Bearer em vez de cookie;
- rate limiting distribuído por Redis, falhando fechado em ambiente protegido;
- access token curto, refresh token opaco com hash, rotação, expiração e revogação;
- decorators de autenticação/permissão no backend e escopo tenant centralizado;
- consultas ORM parametrizadas e identificadores SQL dinâmicos limitados a valores internos validados;
- escaping padrão Jinja; usos de `innerHTML` encontrados apenas limpam nós ou renderizam constantes locais;
- allowlists explícitas de campos de entrada na API, sem mass assignment de modelos;
- rejeição de operações cross-origin e ausência de CORS permissivo;
- erros públicos genéricos com request ID e logs técnicos protegidos;
- `.env` ignorado, exemplos sem credenciais reais e validação de secrets em ambientes protegidos;
- banco e Redis sem portas públicas nos Compose; redes e volumes separados entre HML e PROD;
- health checks públicos com resposta mínima;
- backups pré-deploy e agendados, com retenção configurável;
- imports com extensão permitida, limite global de 8 MiB e validação de schema/tipos;
- nenhuma vulnerabilidade conhecida encontrada por `pip-audit` nas dependências declaradas.

## Implementado, mas melhorado nesta revisão

### ALTO — estado anônimo preservado após autenticação

- Arquivo: `app/routes/auth.py`
- Risco: dados controlados antes do login permaneciam na sessão autenticada. Apesar de a
  sessão Flask ser assinada e não possuir ID servidor fixável, renovar o estado reduz o
  impacto de session fixation e de dados anônimos residuais.
- Correção: limpeza da sessão antes de `login_user`, renovação de permanência e preservação
  apenas do callback desktop estritamente necessário.

### MÉDIO — política de framing permissiva

- Arquivo: `app/__init__.py`
- Risco: `SAMEORIGIN` e `frame-ancestors 'self'` permitiam enquadramento por páginas da
  mesma origem, desnecessário para o produto.
- Correção: `X-Frame-Options: DENY` e `frame-ancestors 'none'`.

### MÉDIO — HSTS abrangia subdomínios sem garantia operacional

- Arquivo: `app/__init__.py`
- Risco: `includeSubDomains` poderia indisponibilizar um subdomínio futuro ainda sem HTTPS.
- Correção: HSTS de um ano apenas para o host atual, sem `includeSubDomains` e sem preload.

### MÉDIO — importação de produtos sem limite próprio de linhas/descompressão

- Arquivo: `app/routes/catalog.py`
- Risco: CSVs com muitas linhas ou XLSX altamente comprimidos poderiam elevar consumo de
  memória/CPU mesmo respeitando o limite do corpo HTTP.
- Correção: máximo de 10.000 linhas, 64 colunas e 32 MiB descompactados para XLSX.

### ALTO — HTTPS da API perdido entre os proxies de homologação

- Arquivo: `deploy/nginx/skygest-hml.conf`
- Risco: o TLS termina no gateway Caddy, mas o Nginx substituía
  `X-Forwarded-Proto` pelo protocolo do salto interno (`http`). As rotas de autenticação da
  API recusavam chamadas HTTPS externas com `426 Upgrade Required`.
- Correção: o Nginx de HML sobrescreve um marcador privado com o protocolo validado; a
  aplicação só o aceita quando a confiança em proxies está explicitamente habilitada.
  O deploy também passou a exigir `401` (e recusar `426`) em uma rota autenticada sem token.

## Não implementado / pendências

- **ALTO — usuário administrativo de schema:** `MYSQL_SERVER_DATABASE_URL` ainda usa root
  para criar bancos tenant dinamicamente. Criar na infraestrutura uma conta separada apenas
  com `CREATE/DROP` sobre o prefixo tenant e retirar root da aplicação exige rotação de
  credenciais e teste de provisionamento/restauração.
- **MÉDIO — usuário do container:** a imagem não declara `USER`; executar Gunicorn como
  usuário não-root requer validar permissões dos volumes de logs, backups e previews.
- **MÉDIO — CSP inline:** a CSP ainda permite `unsafe-inline` para scripts/estilos por
  compatibilidade com templates existentes. A remoção deve ser incremental com nonces/hashes
  e observação prévia em report-only.
- **MÉDIO — restore drill:** existem backups e retenção, mas a proteção só fica completa com
  restauração periódica documentada em ambiente isolado.
- **BAIXO — TLS externo:** versões/ciphers e ocultação de versão dependem do gateway HTTPS
  da OCI; devem ser confirmados no servidor, não inferidos apenas do Caddy interno.

## Vulnerabilidades potenciais revisadas sem achado explorável

- IDOR/BOLA em produtos, categorias, vendas, pagamentos, caixa, estoque, contas, usuários,
  notificações, relatórios e auditoria: recursos individuais usam sessão tenant e filtros de
  `company_id`; testes cross-tenant cobrem múltiplos módulos.
- SQL injection: SQL textual usa bind parameters; nomes de bancos/tabelas vêm de allowlists
  ou validadores de identificador.
- XSS: saída de usuário permanece sob autoescape; não foi encontrada renderização de HTML
  fornecido por usuários.
- mass assignment/company spoofing: payloads são lidos campo a campo e o tenant vem do
  usuário autenticado.
- CORS: não há reflexão nem wildcard; requisições mutáveis com `Origin` divergente recebem 403.

## Critérios verificados

- [x] password hashing seguro
- [x] sessões seguras
- [x] cookies Secure/HttpOnly/SameSite
- [x] proteção CSRF
- [x] rate limiting
- [x] proteção contra enumeração de usuários
- [x] autorização backend
- [x] isolamento multiempresa
- [x] IDOR/BOLA
- [x] SQL Injection
- [x] XSS
- [x] mass assignment
- [x] CORS
- [x] security headers e CSP
- [x] tratamento seguro de erros
- [x] secrets
- [x] logs/auditoria
- [x] upload/importação
- [x] dependências
- [x] banco, Docker e reverse proxy (com pendências acima)
- [x] separação HML/PROD
- [x] testes automatizados de segurança

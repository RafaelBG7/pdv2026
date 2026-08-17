# Estado atual completo — 17/08/2026

Este é o documento oficial de continuidade do Girofy a partir do commit mais recente da `main` em 17/08/2026. Ele descreve separadamente Web, App Windows, Backend/API, banco e infraestrutura, além das regras compartilhadas, segurança, testes, publicação e pendências.

## 1. Resumo executivo

O Girofy é um PDV SaaS multiadega com duas interfaces sobre a mesma fonte de verdade:

- **Web:** Flask/Jinja, HTML, CSS e JavaScript, usada para operação, administração da adega e painel master do SaaS.
- **App Windows:** cliente WPF/.NET 8 online, distribuído como executável self-contained e consumidor da API REST v1.
- **Backend/API:** Flask, SQLAlchemy, serviços transacionais, autenticação, permissões, auditoria, alertas e integração com MySQL/Redis.
- **Banco:** banco central para identidade/empresas e banco operacional separado por tenant.

O App não contém banco paralelo, não acessa MySQL diretamente e não executa migrations. Web e Windows podem ter UX nativa diferente, mas regras críticas devem permanecer no backend.

## 2. Limites de responsabilidade

| Camada | Responsabilidade | Não deve fazer |
|---|---|---|
| Web | Renderizar telas, coletar dados, apresentar erros e chamar serviços do servidor | Duplicar cálculo autoritativo de venda, caixa ou estoque |
| App Windows | Apresentar ViewModels, consumir `/api/v1`, proteger sessão e preferências locais | Conectar ao MySQL, aplicar migration ou decidir regra financeira |
| API | Autenticar, autorizar, validar contratos e serializar respostas | Confiar em permissão ou total calculado pelo cliente |
| Serviços | Transações, locks, idempotência, dinheiro, tenant, auditoria e domínio | Conhecer detalhes visuais de Web/WPF |
| Banco | Persistência central e por tenant, constraints e histórico | Ser manipulado diretamente pelo cliente Windows |

## 3. Estrutura do repositório

```text
app/                  Backend Flask, rotas, modelos, serviços, templates e assets Web
desktop_wpf/          Solução .NET 8: Desktop, Application, Infrastructure e testes
docs/                 Documentação técnica, funcional e operacional
migrations/central/   Migrações do banco central
migrations/tenant/    Migrações aplicadas aos bancos das adegas
scripts/              Deploy, migrations, manutenção e infraestrutura OCI
deploy/               Configuração de containers e publicação
tests/                 Testes de integração/contrato Flask
.github/workflows/     Build Windows e deploy OCI
```

## 4. WEB — funções e comportamento

### Autenticação e onboarding

- login por usuário ou e-mail, logout e opção “Lembre de mim”;
- cadastro de adega e primeiro administrador;
- política mínima de senha;
- confirmação de e-mail por código;
- recuperação e redefinição de senha por e-mail;
- solicitação e confirmação de troca de e-mail;
- bloqueio de usuário/empresa inativa ou assinatura expirada;
- autorização elevada por credencial para ações protegidas.

### Administração SaaS `[MASTER_ONLY]`

- dashboard master;
- listagem, edição, acesso assistido, ativação/inativação e exclusão de adegas;
- usuários e assinaturas globais;
- geração, renovação e cancelamento de keys;
- logs e auditoria master;
- acesso temporário a um tenant sem gravar o master como funcionário da adega.

### Catálogo

- cadastro, edição, atualização rápida, ativação/inativação e exclusão de produtos;
- categorias isoladas por adega;
- código de barras único no tenant;
- custo, preço, margem, estoque atual e mínimo;
- produtos kit com baixa no produto-base;
- busca por nome/código, filtro por categoria/status e ordenação;
- detalhes expansíveis do produto;
- importação CSV/XLSX e exportação autorizada.

### Vendas

- caixa aberto obrigatório;
- múltiplos itens e quantidades inteiras;
- busca/autocomplete de produtos;
- desconto monetário validado no servidor;
- dinheiro, Pix, débito e crédito, inclusive pagamentos mistos;
- taxas configuráveis e lucro líquido por item;
- troco e pagamento insuficiente;
- estoque normal, kit e estoque negativo configurável;
- idempotência por empresa e pedido;
- histórico, detalhes, itens, pagamentos e lucro;
- cancelamento com motivo, permissão, devolução exata de estoque e auditoria.

Desde o marco atual, Web e App usam `sale_service.create_sale`: dinheiro é tratado com `Decimal`, caixa/produtos são bloqueados, e reenvio não duplica venda nem baixa de estoque.

### Caixa

- abertura com saldo inicial;
- apenas um caixa aberto por empresa;
- caixa atual e caixas anteriores;
- resumo, saldo esperado/final, total vendido, lucro e diferença;
- formas de pagamento;
- linha do tempo expansível de vendas;
- saldo existente antes de cada venda;
- cancelamentos destacados sem apagar o histórico original;
- fechamento com conferência exata e proteção por permissão.

Abertura e fechamento Web/API usam `cash_register_service`, com lock no escopo da empresa, releitura transacional e auditoria de origem.

### Estoque

- entrada e ajuste manual;
- baixa automática por venda e devolução por cancelamento;
- origem, tipo, motivo, observação, usuário e saldo antes/depois;
- filtros por produto, categoria, tipo, responsável e período;
- estoque mínimo, esgotado e negativo;
- notificações configuráveis por produto.

### Contas, relatórios e auditoria

- contas a pagar: criar, listar, filtrar, pagar e reabrir;
- relatórios por período e produto;
- faturamento, lucro, desconto, ticket médio e itens vendidos;
- pagamentos, produtos mais vendidos e vendas por horário;
- auditoria tenant com ação, entidade, ator, IP, rota, request ID e diffs;
- exportações administrativas e backups manuais/agendados.

### Notificações e e-mail

- alertas de estoque baixo/esgotado e contas próximas/vencidas;
- popover compacto aberto/fechado por clique;
- contador e navegação para a ação necessária;
- preferências por usuário/empresa;
- entregas de e-mail registradas e protegidas contra repetição indevida.

### Tema e acessibilidade

- temas Light/Dark por variáveis CSS;
- toggle sol/lua no login e topbar;
- animação curta, suporte a `prefers-reduced-motion` e sem reload;
- persistência em `localStorage` e aplicação antecipada no `<head>`;
- preferência inicial do sistema por `prefers-color-scheme`;
- tamanho de texto, contraste e negrito opcionais;
- menu lateral colapsável e responsividade.

O seletor textual duplicado foi removido do menu do usuário; o toggle sol/lua é o controle principal.

## 5. APP WINDOWS — funções e arquitetura

### Solução

- `Girofy.Desktop`: WPF, XAML, janela, views, recursos e integração Windows;
- `Girofy.Application`: modelos, abstrações, comandos e ViewModels;
- `Girofy.Infrastructure`: cliente HTTP, sessão, preferências e armazenamento;
- `Girofy.UnitTests`: testes de comandos, ViewModels, contratos e serviços.

### Sessão e conexão

- login e recuperação de senha;
- access token e refresh token rotacionável;
- logout e revogação;
- sessão protegida por mecanismos do Windows;
- endereço do servidor configurável;
- diagnóstico de conexão e mensagens controladas;
- nenhuma credencial ou segredo embutido no executável.

### Módulos disponíveis

- Dashboard;
- Produtos e Categorias;
- Vendas e cancelamento;
- Caixa atual e Caixas anteriores;
- Estoque;
- Contas a pagar;
- Relatórios;
- Auditoria;
- Notificações;
- Configurações, perfil, senha, empresa e equipe;
- importação, exportação e backup via API.

### UX e desempenho

- navegação lateral nativa;
- produtos, vendas e caixas com detalhes expansíveis;
- clique repetido minimiza o item aberto;
- carregamento sob demanda de detalhes;
- virtualização/recycling em tabelas extensas;
- debounce/cancelamento de pesquisa;
- descarte de respostas antigas;
- comandos assíncronos protegidos contra reentrada;
- scroll otimizado e instância única do aplicativo;
- logs locais em `%LocalAppData%/Girofy/logs`;
- handler global que informa erro sem falhar silenciosamente.

### Tema Light/Dark

- `Themes/Colors.xaml` centraliza brushes, gradientes e estilos;
- `WindowsThemeService` aplica a paleta e persiste em preferências JSON;
- preferência carregada antes da janela para evitar flash;
- toggle sol/lua reutilizado no login, topbar e configurações;
- animação do indicador/ícone em 240 ms;
- inputs, ComboBox, DatePicker, DataGrid, cabeçalhos, linhas alternadas, seleção, overlays, modais, alertas, botões, tooltips e scrollbars usam tokens;
- cores principais da marca permanecem coerentes com a Web.

### Distribuição

- target .NET 8, `win-x64`, self-contained;
- publish single-file comprimido;
- testes e compilação executados em `windows-latest`;
- executável atual publicado na release `windows-preview`;
- download permanente: `https://github.com/RafaelBG7/pdv2026/releases/download/windows-preview/Girofy.exe`;
- assinatura Code Signing e instalador formal continuam pendentes.

## 6. BACKEND/API — contratos

### API v1

Prefixo: `/api/v1`. Áreas principais:

- health/dependencies;
- login, refresh, logout, recuperação e usuário atual;
- ativação de assinatura;
- dashboard;
- catálogo/categorias;
- vendas e cancelamento;
- caixa/snapshots/detalhes;
- estoque;
- contas a pagar;
- relatórios;
- auditoria;
- notificações;
- configurações, equipe, importação, exportação e backup.

Respostas de sucesso usam envelope `data`. Erros trazem mensagem, código estável, status HTTP e campo quando aplicável. O cliente não deve depender apenas do texto da mensagem.

### Serviços críticos

- `sale_service`: venda, Decimal, pagamentos, fees, locks, idempotência, estoque e auditoria;
- `cash_register_service`: abertura/fechamento, saldo esperado, locks e snapshots;
- `stock_service`: movimentos e concorrência;
- `product_service`/`category_service`: catálogo por tenant;
- `api_auth_service`: tokens e revogação;
- `audit_service`: eventos e mascaramento;
- `alert_service`/`notification_service`: alertas internos/e-mail;
- `migration_service`: verificação e aplicação das trilhas Alembic.

### Multi-tenant

- toda operação resolve a empresa autenticada;
- consultas incluem `company_id` ou usam a sessão do banco tenant;
- IDs recebidos do cliente são revalidados no tenant;
- chave idempotente é única dentro da empresa;
- permissões são avaliadas no servidor;
- App e Web nunca podem selecionar livremente outro banco.

## 7. BANCO E MIGRATIONS

- **Central:** empresas, usuários, ativação, autenticação e administração SaaS.
- **Tenant:** catálogo, estoque, vendas, pagamentos, caixas, contas, auditoria, notificações e configurações operacionais.
- Flask-Migrate/Alembic possui árvores independentes `central` e `tenant`.
- Revisões head atuais: `central_0002` e `tenant_0002`.
- Produção usa verificação de revisão e falha se o schema estiver atrasado.
- Deploy faz backup antes de migration.
- App Windows não recebe string de conexão e não altera schema.

## 8. SEGURANÇA

- senha com hash e política mínima;
- confirmação de e-mail e tokens expiráveis;
- cookies de sessão e CSRF na Web;
- bearer access/refresh na API;
- rotação e revogação de refresh tokens;
- rate limit persistente/distribuído com Redis;
- fallback e health de dependências observáveis;
- autorização por permissão e elevação controlada;
- isolamento por tenant;
- logs com request ID e campos sensíveis mascarados;
- MySQL/Redis sem exposição pública direta;
- segredos fornecidos por ambiente/GitHub, não pelo repositório.

Antes de produção pública ainda são necessários domínio HTTPS definitivo e assinatura do executável.

## 9. TESTES E QUALIDADE

### Backend/Web

```bash
.venv/bin/python -m unittest tests.test_routes
```

A suíte cobre rotas, autenticação, API, permissões, tenants, vendas, idempotência, caixa, estoque, cancelamento, relatórios, notificações, rate limit, CSRF, migrations e logs.

### Windows

```bash
dotnet restore desktop_wpf/Girofy.Desktop.sln
dotnet test desktop_wpf/tests/Girofy.UnitTests/Girofy.UnitTests.csproj --configuration Release
```

O runner também valida bindings XAML e produz o aplicativo self-contained. Homologação manual em Windows real continua necessária para contraste, resoluções, scroll, teclado, múltiplos cliques, impressão futura e integração com o sistema operacional.

### Critério mínimo de entrega

1. testes Python aprovados;
2. migrations carregam e heads são conhecidos;
3. testes .NET aprovados quando App/contrato é afetado;
4. build Windows aprovado quando App é afetado;
5. health checks aprovados após deploy Web;
6. documentação e matriz atualizadas;
7. nenhum segredo ou artefato binário versionado indevidamente.

## 10. WORKFLOWS E DEPLOY

### Web/API

Workflow: `Deploy OCI Self Hosted`.

```text
checkout → Python/dependências → testes → validação das migrations/scripts
→ runner OCI → backup/migrations/containers → health checks
```

Ambiente atual: `http://168.75.101.126:18080`.

### Windows

Workflow: `Build Windows WPF preview`.

```text
bindings → .NET/Python → contratos backend → restore → testes .NET
→ publish win-x64 self-contained → upload da release Girofy.exe
```

Web e App são publicados separadamente. Uma mudança de contrato compartilhado deve validar ambos. Mudança apenas documental não dispara deploy automaticamente; use `workflow_dispatch` quando uma nova publicação for solicitada.

O aviso de depreciação de Node 20 emitido pelas actions não é uma falha do Girofy: os runners atuais forçam Node 24 e os jobs continuam válidos.

## 11. OBSERVABILIDADE E OPERAÇÃO

- `/health`, `/health/dependencies` e equivalentes da API;
- logs estruturados com request ID;
- logs locais do App;
- auditoria tenant/master;
- status de Redis e banco nos health checks;
- workflows e logs de deploy no GitHub Actions;
- rollback deve respeitar compatibilidade de schema e backup.

## 12. PENDÊNCIAS PRIORIZADAS

### Alta prioridade

1. domínio definitivo e HTTPS;
2. assinatura Code Signing e instalador confiável;
3. homologação funcional/visual completa em Windows real;
4. teste de concorrência contra MySQL real para `FOR UPDATE`;
5. restauração guiada e auditável de backup.

### Média prioridade

1. cobrança real e regras comerciais dos planos;
2. impressão/comprovante e periféricos;
3. cadastro de clientes;
4. cancelamento parcial por item;
5. estorno integrado a adquirentes;
6. política formal de compatibilidade e descontinuação da API v1;
7. testes visuais automatizados Light/Dark.

### Fora da arquitetura atual

Operação offline/sincronização não está implementada. Adicioná-la exigiria banco local, fila, resolução de conflitos, criptografia e estratégia explícita; não deve ser criada como cache improvisado.

## 13. DOCUMENTOS CANÔNICOS

- [Índice](00-INDEX.md)
- [Matriz de plataformas](MATRIX.md)
- [Paridade funcional](FEATURE_PARITY.md)
- [Web](web/README.md)
- [App Windows](app/README.md)
- [Backend compartilhado](shared/README.md)
- [Temas](shared/THEMING.md)
- [Workflows](WORKFLOWS.md)
- [Migrations](29-migracoes-versionadas.md)
- [Segurança](14-seguranca.md)
- [Testes](15-testes.md)

## 14. PONTO OFICIAL DE RETOMADA

O desenvolvimento deve partir do commit desta atualização na branch `main`. Toda nova entrega deve declarar explicitamente `[WEB]`, `[APP]`, `[BACKEND]` e `[DATABASE]`, atualizar a matriz quando houver mudança funcional e executar somente os pipelines necessários — ou ambos quando contrato compartilhado for afetado.

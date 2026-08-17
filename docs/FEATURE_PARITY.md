# Paridade funcional Web, Windows e Backend

Atualizado em 17/08/2026 a partir das rotas Flask, endpoints `/api/v1`, serviços, modelos, ViewModels WPF e workflows do repositório.

## Legenda

- `[WEB_ONLY]`: deliberadamente disponível apenas no navegador.
- `[APP_ONLY]`: comportamento local do cliente Windows.
- `[WEB_APP]`: experiência presente nas duas interfaces.
- `[BACKEND]`: infraestrutura ou endpoint sem tela própria.
- `[SHARED]`: regra central obrigatoriamente reutilizada pelas interfaces.
- `[MASTER_ONLY]`: operação do administrador global SaaS.

## Arquitetura e fonte da verdade

O Flask/API é a fonte de verdade. Dados globais de empresas, usuários e assinatura ficam no banco central; dados operacionais ficam no banco do tenant. O App WPF não acessa MySQL e não executa migrations: chama `/api/v1`, mantém apenas tokens/preferências locais e exige conexão. A Web usa as mesmas sessões tenant e, para operações críticas, os mesmos serviços do endpoint.

## Matriz detalhada

| Recurso | Classificação | Web | Windows | Contrato/regra central | Estado |
|---|---|---|---|---|---|
| Login e logout | `[WEB_APP]` | Cookie Flask-Login | access/refresh token | auth + permissões + assinatura | Paridade funcional |
| Recuperação de senha | `[WEB_APP]` | link/token | solicitação no App | serviço de e-mail/API | Paridade de resultado |
| Cadastro/verificação de adega | `[WEB_ONLY]` | fluxo completo | redirecionamento/ausente | modelos centrais | Diferença intencional |
| Painel master, adegas, keys e logs | `[MASTER_ONLY]` | completo | não exposto | banco central | Diferença intencional |
| Dashboard | `[WEB_APP]` | cards Web | DashboardViewModel | `/dashboard/summary` | Paridade |
| Produtos e kits | `[WEB_APP]` | Jinja/catalog | CatalogViewModel | product_service/API | Paridade |
| Categorias | `[WEB_APP]` | CRUD | CatalogViewModel | category_service/API | Paridade |
| Venda | `[SHARED]` | formulário PDV | SalesViewModel | `sale_service.create_sale` | Corrigido |
| Idempotência de venda | `[SHARED]` | chave oculta por pedido | chave por requisição | `ApiSaleRequest`, única por empresa | Corrigido |
| Concorrência de venda/estoque | `[SHARED]` | serviço comum | serviço comum | locks no caixa/produtos, transação atômica | Corrigido |
| Cancelamento de venda | `[SHARED]` | detalhe da venda | SalesViewModel | `cancel_sale`, estoque e auditoria | Paridade |
| Caixa | `[SHARED]` | atual/anteriores | CashRegisterViewModel | `cash_register_service` | Corrigido |
| Estoque | `[WEB_APP]` | entrada/ajuste/histórico | StockViewModel | stock_service + movimentos | Paridade |
| Contas a pagar | `[WEB_APP]` | tela e filtros | PayablesViewModel | endpoints payables | Paridade |
| Relatórios | `[WEB_APP]` | gráficos/tabelas | ReportsViewModel | endpoints summary/products | Paridade de dados |
| Auditoria | `[WEB_APP]` | tenant e master | AuditViewModel | audit_service | Paridade no tenant |
| Notificações e e-mail | `[WEB_APP]` | menu compacto | NotificationsViewModel | alert/notification services | Paridade |
| Configurações/equipe | `[WEB_APP]` | configurações | SettingsViewModel | settings/team API | Paridade principal |
| Tema claro/escuro | `[WEB_APP]` | localStorage/CSS | preferência local WPF | não altera regra de negócio | Paridade visual |
| DPAPI para tokens | `[APP_ONLY]` | N/A | armazenamento protegido | Windows Credential/Data Protection | Implementado |
| Health/dependencies | `[BACKEND]` | rota operacional | usado para diagnóstico | banco + Redis | Implementado |
| Rate limit distribuído | `[BACKEND]` | transparente | transparente | Redis com fallback controlado | Implementado |
| Migrations Alembic | `[BACKEND]` | deploy aplica | App não aplica | trilhas central/tenant | Implementado |

## Correções críticas desta revisão

Antes desta revisão, `/vendas/nova` calculava e gravava a venda diretamente com `float`, enquanto o Windows usava `sale_service`. Isso permitia diferenças em arredondamento, idempotência, locks e tratamento de concorrência. A Web agora monta `SaleLineInput`/`SalePaymentInput` e chama o mesmo serviço do App. Cada formulário recebe uma chave idempotente; reenvios não criam outra venda nem baixam estoque novamente.

Abertura e fechamento Web também passaram para `cash_register_service`, que serializa o escopo da empresa, bloqueia o caixa em alteração, calcula o valor esperado no servidor e registra auditoria. O serviço aceita a origem (`web` ou `windows_native`) sem duplicar regras.

O isolamento multi-tenant permanece obrigatório em consultas, chave idempotente e locks. Um usuário master operando dentro de uma adega não é gravado como usuário daquela empresa.

## Contratos críticos

### Venda

Entrada: empresa autenticada, ator, itens (`product_id`, quantidade inteira positiva), pagamentos (`method`, valor monetário), desconto e chave idempotente. O servidor valida tenant, status do produto, kit, estoque, caixa aberto, desconto e pagamento. Valores monetários usam `Decimal` com duas casas. A transação grava pedido idempotente, venda, itens, pagamentos, movimentos e auditoria; qualquer falha causa rollback.

### Caixa

Somente um caixa pode estar aberto por empresa. A abertura bloqueia o escopo da empresa. O fechamento bloqueia e relê o caixa, rejeita ID desatualizado e exige `saldo inicial + vendas válidas`. Cancelamentos preservam o histórico de caixa fechado e ficam auditáveis.

### Erros

A API retorna erro estruturado com mensagem, código, status HTTP e campo quando aplicável. A Web traduz o mesmo `OperationError` para mensagem visível e rollback. Códigos são estáveis; texto pode ser aprimorado sem quebrar o App.

## Testes de paridade e risco

- venda API atômica e idempotente;
- reenvio da mesma venda Web cria uma venda, um pedido idempotente e uma baixa;
- venda de kit baixa exatamente o produto-base;
- estoque insuficiente respeita a configuração da empresa;
- caixa exige valor exato e usa o mesmo serviço na Web/API;
- cancelamento restaura estoque uma vez;
- permissões e dados são testados por tenant;
- App possui testes unitários de ViewModels, serviços HTTP, tema e sessão.

## Pendências priorizadas

| Prioridade | Item | Motivo/critério de conclusão |
|---|---|---|
| Alta | Teste concorrente em MySQL real | SQLite não reproduz integralmente `FOR UPDATE`; executar duas vendas simultâneas no pipeline de integração. |
| Alta | HTTPS e assinatura do executável | Proteção de credenciais e confiança do Windows para produção pública. |
| Média | Versionar formalmente `/api/v1` | Definir janela de compatibilidade e processo de descontinuação antes de criar v2. |
| Média | Restauração guiada de backup | Validar, simular, restaurar e auditar pela interface. |
| Média | Testes visuais automatizados | Detectar divergências de tema/layout sem misturar regra de negócio. |
| Baixa | Cadastro completo no App | Implementar somente se houver necessidade comercial; hoje a Web é o canal de onboarding. |
| Fora do escopo atual | Offline/sincronização | Exigiria fila, conflitos e armazenamento local; não deve ser improvisado. |

## Regra para novas funcionalidades

Toda regra que altera venda, caixa, estoque, permissão ou tenant deve nascer em `app/services` e ser exposta pela API. Web e Windows podem ter UX diferente, mas não podem recalcular a regra separadamente. A entrega deve incluir teste de serviço/rota, teste de isolamento e atualização desta matriz.

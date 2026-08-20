# Paridade funcional Web, Windows e Backend

Atualizado em 19/08/2026 a partir das rotas Flask, endpoints `/api/v1`, serviços, modelos, ViewModels WPF, XAML e testes do repositório. Esta matriz registra comportamento comprovado no código; tela parecida não é considerada paridade por si só. A documentação canônica está em `documentacao/DOCUMENTACAO_COMPLETA.txt`.

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
| Produtos | `[WEB_APP]` | CRUD amplo | CatalogViewModel | product_service/API | Paridade parcial |
| Kits | `[WEB_APP]` | cria/edita componente | editor nativo de base e consumo | API valida tenant, atividade, quantidade e autorreferência | Paridade funcional |
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
| Configurações/equipe | `[WEB_APP]` | configurações | SettingsViewModel | settings/team API | Paridade principal, com exceções abaixo |
| Tema claro/escuro | `[WEB_APP]` | localStorage/CSS | preferência local WPF | não altera regra de negócio | Paridade visual |
| DPAPI para tokens | `[APP_ONLY]` | N/A | armazenamento protegido | Windows Credential/Data Protection | Implementado |
| Health/dependencies | `[BACKEND]` | rota operacional | usado para diagnóstico | banco + Redis | Implementado |
| Rate limit distribuído | `[BACKEND]` | transparente | transparente | Redis com fallback controlado | Implementado |
| Migrations Alembic | `[BACKEND]` | deploy aplica | App não aplica | trilhas central/tenant | Implementado |

## Auditoria detalhada por ação — 19/08/2026

Legenda de situação: `OK`, `DIVERGÊNCIA VISUAL`, `DIVERGÊNCIA FUNCIONAL`, `REGRA DIFERENTE`, `PERMISSÃO DIFERENTE`, `CONTRATO API AUSENTE`, `CAMPO AUSENTE`, `VALIDAÇÃO AUSENTE`, `ERRO DE UX`, `BUG`, `EXCLUSIVO WEB POR DECISÃO`, `EXCLUSIVO APP POR DECISÃO` e `NÃO APLICÁVEL`.

### Dashboard, autenticação e sessão

| Módulo | Ação/recurso | Web | App | Backend/API | Situação | Ação |
|---|---|---|---|---|---|---|
| Dashboard | resumo diário | Cards | Cards nativos | `/dashboard/summary` | OK | Nenhuma |
| Dashboard | venda rápida | Link/ação | Botão e F3 | caixa é revalidado | OK | Nenhuma |
| Dashboard | estoque baixo e recentes | Exibe | Exibe | snapshot único | OK | Nenhuma |
| Autenticação | login | Cookie | access/refresh | `/auth/login` | OK | Nenhuma |
| Autenticação | lembrar usuário | Sessão/cookie | preferência local | regras distintas por plataforma | OK | Documentar diferença |
| Autenticação | cadastro e confirmação | Completo | abre fluxo Web | backend central | EXCLUSIVO WEB POR DECISÃO | Manter onboarding Web |
| Autenticação | recuperação | Formulário e reset | solicita e-mail | `/auth/password-recovery/request` | OK | Reset continua no link Web |
| Sessão | renovação | sessão Flask | refresh rotacionado | `/auth/refresh` | OK | Nenhuma |
| Sessão | logout/revogação | POST | comando assíncrono | `/auth/logout` | OK | Nenhuma |
| Assinatura | ativação | Completa | ativação disponível | `/subscription/activate` | OK | Gestão comercial permanece Web |
| Master SaaS | empresas, keys e suporte | Completo | Não exposto | rotas centrais | EXCLUSIVO WEB POR DECISÃO | Manter fora do App operacional |

### Produtos e categorias

| Módulo | Ação/recurso | Web | App | Backend/API | Situação | Ação |
|---|---|---|---|---|---|---|
| Produtos | listar e paginar | 20/página | 50/página | paginação configurável | OK | Diferença de UX intencional |
| Produtos | nome/código | Pesquisa única | Pesquisa única | `q` cobre ambos | OK | Nenhuma |
| Produtos | categoria/status | Filtros | Filtros | suportados | OK | Nenhuma |
| Produtos | estoque/preço | Filtros por disponibilidade, estoque baixo, sem estoque e faixa de preço | Mesmos filtros da Web | `stock`, `min_price` e `max_price` validados e isolados por empresa | OK | Entregue em 20/08/2026 |
| Produtos | ordenação | nome/preço/estoque/criação | nome/preço/estoque/mais recentes/mais antigos | `created_desc` e `created_asc` com desempate por ID | OK | Entregue em 20/08/2026 |
| Produtos | detalhes | Expansível | Expansível | payload de catálogo | OK | Nenhuma |
| Produtos | criar/editar campos básicos | Completo | Modal nativo | POST/PUT products | OK | Nenhuma |
| Produtos | ativar/inativar | Ação dedicada | campo Ativo no editor | PUT products | OK | UX diferente, regra equivalente |
| Produtos | excluir | Confirma e protege histórico | Confirma e chama API | DELETE com permissão, tenant e conflitos | OK | Corrigido nesta auditoria |
| Produtos | margem | Exibe | Exibe quando autorizado | payload traz lucro/margem | OK | Campo e formatação corrigidos nesta auditoria |
| Produtos | kits | Cria/edita base e consumo | Cria/edita base e consumo | POST/PUT validam tenant, atividade, quantidade e autorreferência | OK | Contrato e editor corrigidos nesta auditoria |
| Produtos | estoque manual | Edição gera movimento | Edição gera movimento | stock_service | OK | Nenhuma |
| Categorias | listar/criar/editar/excluir | Completo | Completo em popup | CRUD completo | OK | Nenhuma |
| Categorias | pesquisa | Parâmetro disponível | Campo nativo com Pesquisar, Enter e Limpar | API tenant aceita `q` | OK | Entregue no App em 20/08/2026 |
| Categorias | exclusão com produtos | Rejeita/valida | mostra erro API | category_service | OK | Nenhuma |

### Vendas e caixa

| Módulo | Ação/recurso | Web | App | Backend/API | Situação | Ação |
|---|---|---|---|---|---|---|
| Vendas | exigir caixa aberto | Sim | Sim | sale_service | OK | Nenhuma |
| Vendas | pesquisa/autocomplete | Sim | Até 20 sugestões ranqueadas, densas, virtualizadas, com debounce/cancelamento | catálogo tenant retorna até 30 | OK | Modal responsivo e teclado aprimorados em 19/08/2026 |
| Vendas | seleção de quantidade | Modal Web | Modal WPF equivalente | valida novamente | OK | Entregue em `0d14e87` |
| Vendas | múltiplos itens/alteração/remoção | Sim | Sim | itens revalidados | OK | Nenhuma |
| Vendas | desconto | Sim | Popup | servidor limita | OK | Nenhuma |
| Vendas | dinheiro/Pix/débito/crédito/misto | Sim | Sim | pagamentos validados | OK | Nenhuma |
| Vendas | falta/troco/taxas/lucro | Exibe | Exibe | servidor recalcula | OK | Nenhuma |
| Vendas | estoque negativo e kit | Sim | payload comum | sale_service | OK | Cadastro de kit também disponível no App |
| Vendas | idempotência/duplo clique | Chave por pedido | chave por pedido/comando ocupado | ApiSaleRequest | OK | Nenhuma |
| Vendas | histórico/detalhe | Sim | Sim, expansível | `/sales/today` e `/<id>` | OK | Nenhuma |
| Vendas | cancelamento/motivo/permissão | Sim | Sim | `/cancel`, rollback de estoque e auditoria | OK | Nenhuma |
| Caixa | abrir/fechar/único aberto | Sim | Sim | cash_register_service | OK | Nenhuma |
| Caixa | atual/resumo/pagamentos | Sim | Sim | snapshot comum | OK | Nenhuma |
| Caixa | anteriores/detalhe/timeline | Sim | Sim, expansível com o mesmo template do caixa atual | summary/detail + `/sales/<id>` sob demanda | OK | Detalhe completo entregue em 19/08/2026 |
| Caixa | detalhe auditável da venda | Sim | itens históricos, unitário, quantidade, subtotal, desconto, total, pagamentos, troco, operador, status e cancelamento | `/sales/<id>` revalida sessão e tenant | OK | Cache por ID e erro/retry local no App |
| Caixa | saldo antes/depois da venda | Sim | Sim, separado do resumo da venda | detail calcula sequência | OK | Nenhuma |
| Caixa | conferência e diferença | Sim | Sim | servidor calcula | OK | Nenhuma |

### Estoque, contas e relatórios

| Módulo | Ação/recurso | Web | App | Backend/API | Situação | Ação |
|---|---|---|---|---|---|---|
| Estoque | movimentos/filtros/paginação | Sim | Sim | `/stock/movements` | OK | Nenhuma |
| Estoque | entrada e ajuste | Sim | Sim | stock_service | OK | Nenhuma |
| Estoque | motivo/saldos/origem/responsável | Sim | Sim | payload de movimento | OK | Nenhuma |
| Estoque | baixa/devolução automática | Sim | Reflete | sale_service | OK | Nenhuma |
| Contas | listar/criar/pagar/reabrir | Sim | Sim | endpoints payables | OK | Nenhuma |
| Contas | editar conta existente | Não | Não | endpoint ausente | NÃO APLICÁVEL | Definir como feature futura se necessário |
| Contas | status e alertas | Sim | Sim | backend/notificações | OK | Nenhuma |
| Relatórios | período e indicadores | Sim | Sim | `/reports/summary` | OK | Nenhuma |
| Relatórios | pagamentos/produtos/horários | Sim | Sim | mesma agregação | OK | Nenhuma |
| Relatórios | representação gráfica | HTML/CSS | WPF nativo | mesmos números | DIVERGÊNCIA VISUAL | Intencional, validar visualmente |

### Administração, alertas e UX local

| Módulo | Ação/recurso | Web | App | Backend/API | Situação | Ação |
|---|---|---|---|---|---|---|
| Auditoria | filtros/paginação/detalhe | Sim | Sim | `/audit/logs` | OK | Nenhuma |
| Auditoria | escopo master | Sim | Não | rotas master | EXCLUSIVO WEB POR DECISÃO | Manter |
| Notificações | listar/contagem/ler/ler todas/dispensar | Sim | Popover | endpoints dedicados | OK | Nenhuma |
| Notificações | preferências internas | Sim | Editor completo no painel Alertas | GET/PUT preferences | OK | Entregue em 20/08/2026 |
| Alertas por e-mail | canal, destinatários, severidade e resumo | Sim | Sim, respeitando `can_manage_settings` | backend possui settings/delivery | OK | Destinatários protegidos por permissão |
| Perfil | nome/sobrenome/telefone | Sim | Sim | `/settings/profile` | OK | Nenhuma |
| Perfil | troca de e-mail confirmada | Sim | abre Web | token/serviço Web | EXCLUSIVO WEB POR DECISÃO | Manter por segurança |
| Senha | atual/nova/confirmação | Sim | Sim | `/settings/password` | OK | Nenhuma |
| Equipe | listar/criar/editar/ativar | Sim | Sim | settings/team | OK | Nenhuma |
| Equipe | papéis e flags de permissão | Sim | Sim | servidor revalida | OK | Auditar cada botão continuamente |
| Operação | estoque negativo | Sim | Sim | company settings | OK | Nenhuma |
| Financeiro | taxas Pix/débito/crédito | Sim | Sim | company settings | OK | Nenhuma |
| Backup | status/frequência/manual | Sim | Sim | backup endpoints | OK | Restauração continua pendente |
| Importação | CSV/XLSX e erros | Sim | Seletor nativo | API import | OK | Nenhuma |
| Exportação | tipos/permissão/download | Sim | Salva arquivo | API export | OK | Nenhuma |
| Suporte | informações completas | Sim | atalhos/abre Web | sem regra crítica | DIVERGÊNCIA VISUAL | Intencional |
| Acessibilidade | fonte/negrito/contraste | Sim | direciona à Web | preferência Web | DIVERGÊNCIA FUNCIONAL | Implementar localmente antes do freeze ou documentar exclusão |
| Tema | claro/escuro persistente | Sim | Sim, animado | local por cliente | OK | Nenhuma |
| Rede | timeout/indisponível/cancelamento | navegador | mensagens e async | códigos estruturados | OK | Ampliar testes de integração |
| Rede | 401/refresh | sessão Web | renovação automática | auth service | OK | Nenhuma |
| Rede | 403/404/409/422/429/500 | feedback Web | GirofyApiException/mensagem segura | envelope de erro | OK | Manter testes de contrato |

## Resultado quantitativo desta auditoria

- módulos/áreas principais auditados: 30;
- ações/recursos explicitamente classificados nesta matriz: 73;
- totalmente equivalentes ou equivalentes por comportamento: 60;
- diferenças intencionais/exclusivas ou não aplicáveis: 6;
- divergências visuais/funcionais/campos pendentes: 6;
- linhas classificadas como contrato ausente: 1; os contratos de filtros avançados de produto, ordenação por criação, pesquisa de categorias e preferências de notificações nativas foram concluídos em 20/08/2026; a acessibilidade avançada permanece como divergência funcional;
- status: `PARIDADE WEB × APP × BACKEND: EM EVOLUÇÃO`.

As contagens agrupam linhas relacionadas e devem ser atualizadas quando uma ação mudar de classificação. Não transformar este número em percentual de marketing.

## Correções críticas desta revisão

Antes desta revisão, `/vendas/nova` calculava e gravava a venda diretamente com `float`, enquanto o Windows usava `sale_service`. Isso permitia diferenças em arredondamento, idempotência, locks e tratamento de concorrência. A Web agora monta `SaleLineInput`/`SalePaymentInput` e chama o mesmo serviço do App. Cada formulário recebe uma chave idempotente; reenvios não criam outra venda nem baixam estoque novamente.

Abertura e fechamento Web também passaram para `cash_register_service`, que serializa o escopo da empresa, bloqueia o caixa em alteração, calcula o valor esperado no servidor e registra auditoria. O serviço aceita a origem (`web` ou `windows_native`) sem duplicar regras.

O isolamento multi-tenant permanece obrigatório em consultas, chave idempotente e locks. Um usuário master operando dentro de uma adega não é gravado como usuário daquela empresa.

Produtos agora possuem o mesmo contrato de exclusão segura na Web e no App: o serviço central bloqueia exclusão quando há venda registrada ou quando o produto é base de kit, preserva histórico, valida tenant/permissão e audita a operação. O contrato `DELETE /api/v1/catalog/products/<id>` foi criado para o Windows. A mutação de kits em `POST/PUT /api/v1/catalog/products` passou a aceitar produto-base e quantidade consumida; o servidor rejeita componente de outro tenant, inativo, ausente ou autorreferente. O editor WPF envia esses campos e exibe composição e margem no detalhe expansível.

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

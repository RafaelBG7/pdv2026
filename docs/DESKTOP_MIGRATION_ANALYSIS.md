# Análise da Migração Windows Nativa

## Objetivo

O Girofy web continua sendo o produto estável e permanece publicado na OCI em:

```text
http://168.75.101.126:18080
```

A eventual versão Windows é desenvolvida separadamente em `desktop_wpf/`. Ela usa
C#, .NET 8, WPF e MVVM, com telas realmente nativas e integração exclusivamente pela
API REST do Flask. Nenhuma etapa dessa migração substitui ou interrompe a versão web.

Para a separação atual entre versão web e Windows, veja também:

```text
docs/24-estado-versoes-web-windows.md
```

## Estado Atual

Já existem no cliente WPF:

- solução separada em camadas Application, Infrastructure, Desktop e UnitTests;
- configuração segura do endereço da API;
- verificação de conectividade em `GET /api/v1/health`;
- login por usuário ou e-mail;
- ativação de assinatura vencida por key diretamente no cliente Windows;
- access token curto e refresh token rotativo;
- sessão local protegida pelo DPAPI do Windows;
- restauração de sessão, logout e revogação de token;
- opção de lembrar apenas o identificador do usuário;
- shell autenticado com navegação entre Dashboard, Produtos, Categorias, Caixa, Vendas,
  Estoque, Relatórios, Contas a pagar, Auditoria e Configurações;
- dashboard operacional agregado e isolado por adega;
- caixa atual, vendas do dia, ticket, lucro conforme permissão, pagamentos, estoque baixo,
  produtos mais vendidos e vendas recentes;
- API de catálogo paginada, filtrada pela empresa do token;
- busca, filtros, ordenação e tabelas WPF virtualizadas;
- carregamento do catálogo sob demanda, sem consulta automática após o login;
- cadastro e edição básica de produtos no cliente nativo;
- cadastro, edição e exclusão de categorias no cliente nativo;
- endpoints versionados para criar e atualizar produtos, com validação de permissão,
  duplicidade, categoria da adega, ajuste de estoque e auditoria;
- endpoints versionados para criar, atualizar e excluir categorias, com validação por
  adega, bloqueio de exclusão com produtos vinculados e auditoria;
- consulta sob demanda do caixa atual e dos dez caixas fechados mais recentes;
- abertura e fechamento transacionais de caixa com conferência exata, proteção de
  permissão, auditoria e valores financeiros redigidos quando necessário;
- venda nativa com pesquisa, carrinho, quantidades, desconto, pagamentos combinados,
  troco e comprovante;
- criação transacional da venda no banco da adega, com baixa de estoque, suporte a kits,
  taxas da maquininha, auditoria e caixa obrigatório;
- idempotência para recuperação segura após falhas de conexão, sem venda duplicada;
- preservação do pedido após erros de validação ou comunicação;
- estoque operacional nativo com histórico paginado, filtros, resumo de entradas/saídas e
  produtos movimentados;
- entrada manual e ajuste manual de estoque pelo cliente WPF, sempre executados pelos
  endpoints versionados e pelo `stock_service` do servidor;
- API de estoque protegida por `can_view_stock_movements` e `can_manage_stock`, com
  auditoria e isolamento por adega;
- relatórios nativos com períodos diário, semanal, mensal, anual e personalizado;
- resumo de vendas, itens, subtotal, desconto, total final, lucro, ticket médio, formas de
  pagamento, gráfico agregado e produtos mais vendidos;
- API de relatórios em `GET /api/v1/reports/summary`, protegida por `can_view_reports` e
  agregada no backend para manter o cliente leve;
- relatório nativo por produto em `GET /api/v1/reports/products`, com paginação,
  busca, ordenação, quantidade vendida, faturamento, custo, lucro, ticket médio e estoque;
- contas a pagar nativas com listagem, filtros, cadastro, pagamento e reabertura;
- auditoria nativa com filtros, paginação e detalhes expansíveis;
- configurações nativas para perfil, senha, regras operacionais da adega, taxas de
  Pix/débito/crédito, backup, importação de produtos, exportação e gestão básica de
  equipe;
- frequência de backup e geração manual integradas aos endpoints versionados, sempre
  usando a adega presente no token;
- endpoint versionado para ativar assinatura em `POST /api/v1/subscription/activate`,
  validando usuário, senha e key antes de emitir a sessão;
- logs locais rotativos sem senha ou token completo;
- workflow Windows para testes e build de prévia.

O backend mantém autenticação, tenant, assinatura, permissões e regras de negócio como
fonte de verdade. O cliente nunca acessa o MySQL diretamente.

## Princípios da Migração

1. Preservar integralmente o Flask/Jinja e o deploy OCI.
2. Criar endpoints versionados em `/api/v1` sem duplicar regras de negócio.
3. Exigir HTTPS para credenciais e tokens fora de desenvolvimento controlado.
4. Migrar um módulo de cada vez, começando por consultas somente leitura.
5. Aplicar paginação, cancelamento e virtualização para manter baixo consumo.
6. Tratar vendas e caixa com idempotência e validação transacional no servidor.
7. Manter testes de contrato entre API e cliente nativo.

## Ordem Recomendada

1. Publicar a OCI atrás de domínio e HTTPS.
2. Ampliar detalhes de produtos e finalizar manutenção avançada de catálogo.
3. Aprofundar relatórios de caixa e comparativos.
4. Migrar importação e permissões administrativas avançadas restantes.
5. Preparar assinatura digital e instalador quando o cliente nativo alcançar paridade
   suficiente com o fluxo web. A atualização automática está pausada/cancelada por decisão
   de produto.

## Progresso Funcional

Estimativa atual: **91% da migração Windows planejada**.

- concluído: fundação nativa, conexão, autenticação/sessão, shell, dashboard, consulta de
  produtos/categorias, cadastro e edição básica de produtos, manutenção de categorias,
  abertura/fechamento de caixa, registro de vendas, estoque operacional e resumo de
  relatórios, relatório por produto, contas a pagar, auditoria, configurações pessoais,
  regras operacionais da adega, taxas de Pix/débito/crédito, backup, importação de
  produtos, exportação CSV, gestão básica de equipe e ativação por key;
- parcial: histórico detalhado de caixa/vendas, manutenção avançada de catálogo e
  algumas configurações financeiras avançadas ainda dependem da versão web;
- pendente: instalador assinado e HTTPS público;
- pausado por decisão de produto: atualização automática do cliente Windows.

O percentual mede módulos funcionais necessários para paridade operacional e pode mudar
quando o escopo de produção for refinado. A versão web permanece integralmente disponível.

## Critério de Liberação

O WPF só deve ser distribuído para clientes quando os módulos necessários estiverem
completos, os endpoints estiverem protegidos por HTTPS, os testes Windows passarem e a
versão web continuar disponível como contingência.

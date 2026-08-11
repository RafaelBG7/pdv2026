# 09 - Rotas HTTP

## Nota Importante

O projeto ainda opera principalmente com rotas web HTML, renderização Jinja2 e submissão de formulários. A partir da preparação para o cliente desktop nativo, existe também uma fundação de API JSON versionada em `/api/v1`.

Esta documentação descreve os endpoints HTTP atuais. A API JSON usa sempre o envelope:

```json
{
  "success": true,
  "data": {},
  "message": null,
  "errors": []
}
```

Em falhas, `success` é `false`, `data` é `null` e `errors` contém `field`, `code` e `message`.
Todas as respostas da API recebem `Cache-Control: no-store`.

## API JSON Versionada

### `GET /api/v1/health`

Descrição: verifica se a API versionada está disponível.

Permissão: pública.

Resposta:

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "service": "girofy",
    "api_version": "v1"
  },
  "message": null,
  "errors": []
}
```

Cabeçalhos:

- `Cache-Control: no-store`

Observação: o endpoint legado `GET /health` continua existindo para compatibilidade com deploy, health checks e clientes desktop já empacotados.

### Transporte seguro

Os endpoints em `/api/v1/auth/*` exigem HTTPS. Em produção, `API_ALLOW_INSECURE_AUTH`
deve permanecer `0`. Quando o Flask estiver atrás de um proxy reverso HTTPS confiável,
configure `TRUST_PROXY_HEADERS=1` para aceitar `X-Forwarded-Proto: https`.

O IP OCI atual em `http://168.75.101.126:18080` pode responder ao health check, mas a
autenticação retorna HTTP `426` por padrão. `API_ALLOW_INSECURE_AUTH=1` existe somente
para testes controlados e transmite credenciais sem criptografia.

## Autenticação da API

### `POST /api/v1/auth/login`

Descrição: autentica o aplicativo Windows e cria uma sessão revogável.

Permissão: pública, limitada por IP + identificador.

Payload:

```json
{
  "identifier": "operador-ou-email@example.com",
  "password": "SenhaForte123"
}
```

Sucesso: HTTP `200`, com access token de curta duração, refresh token rotativo,
identidade, empresa e permissões.

```json
{
  "success": true,
  "data": {
    "access_token": "token-assinado",
    "refresh_token": "grf1.sessao.segredo",
    "token_type": "Bearer",
    "expires_in": 900,
    "refresh_expires_at": "2026-08-14T12:00:00Z",
    "user": {
      "id": 10,
      "username": "operador",
      "full_name": "Operador Girofy",
      "role": "operator",
      "role_label": "Funcionário",
      "permissions": {}
    },
    "company": {
      "id": 4,
      "name": "Adega JF",
      "active": true,
      "subscription_valid": true
    }
  },
  "message": null,
  "errors": []
}
```

Validações aplicadas:

- senha verificada pelo hash existente do usuário;
- e-mail confirmado;
- usuário e empresa ativos;
- assinatura válida, exceto para o master do sistema;
- no máximo `API_LOGIN_ATTEMPT_LIMIT` falhas antes do bloqueio temporário;
- auditoria de login bem-sucedido e tentativa inválida.

Erros principais: `invalid_credentials`, `email_not_verified`, `user_inactive`,
`company_inactive`, `subscription_required`, `login_rate_limited` e `https_required`.

### `POST /api/v1/subscription/activate`

Descrição: ativa uma assinatura/key pelo cliente Windows quando o login normal retorna
`subscription_required`. Esse endpoint não libera acesso sem autenticação: ele exige o
mesmo usuário e senha do login e aplica a key somente na adega vinculada àquele usuário.

Permissão: pública, limitada por IP + identificador, com transporte seguro obrigatório.

Payload:

```json
{
  "identifier": "adegajf",
  "password": "SenhaForte123",
  "activation_key": "ABCD-1234-EFGH-5678"
}
```

Sucesso: HTTP `200`, com a mesma estrutura de sessão do login: access token, refresh
token rotativo, usuário, empresa, permissões e status atualizado da assinatura.

Validações aplicadas:

- usuário e senha precisam ser válidos;
- e-mail confirmado, usuário ativo e empresa ativa continuam obrigatórios;
- usuário master do sistema não ativa key de adega por esse endpoint;
- a key precisa existir, estar ativa, não usada e não expirada;
- a key é marcada como usada e vinculada à empresa do usuário;
- plano, início da assinatura, renovação, ciclo e key atual da adega são atualizados;
- a ativação gera auditoria `subscription_activated`.

Erros principais: `identifier_required`, `password_required`, `activation_key_required`,
`invalid_credentials`, `email_not_verified`, `user_inactive`, `company_inactive`,
`company_context_required`, `invalid_activation_key`, `login_rate_limited` e
`https_required`.

### `POST /api/v1/auth/refresh`

Descrição: troca um refresh token válido por um novo par de tokens. O token anterior é
revogado no mesmo processo e não pode ser reutilizado.

Payload:

```json
{
  "refresh_token": "grf1.sessao.segredo"
}
```

Sucesso: HTTP `200`, com a mesma estrutura de `data` do login.

Erros principais: `invalid_refresh_token`, `credentials_changed`,
`subscription_required` e `https_required`.

### `GET /api/v1/auth/me`

Descrição: retorna a identidade, a empresa e as permissões atuais. O servidor revalida
status do usuário, empresa, assinatura e alteração de senha.

Permissão: Bearer access token.

Cabeçalho:

```text
Authorization: Bearer ACCESS_TOKEN
```

### `POST /api/v1/auth/logout`

Descrição: revoga a sessão correspondente ao access token.

Permissão: Bearer access token.

Resposta:

```json
{
  "success": true,
  "data": {
    "logged_out": true
  },
  "message": null,
  "errors": []
}
```

### Ciclo de vida dos tokens

- access token: assinado com `API_TOKEN_SECRET`, padrão de 15 minutos;
- refresh token: segredo aleatório, padrão de 30 dias;
- somente o hash do refresh token é salvo no MySQL;
- refresh tokens são rotacionados a cada renovação;
- logout, alteração de senha, inativação ou vencimento podem invalidar o acesso;
- o cliente WPF protege a sessão com DPAPI no perfil do usuário Windows;
- senhas nunca são persistidas pelo cliente.

## Dashboard da API

### `GET /api/v1/dashboard/summary`

Descrição: retorna uma visão agregada da operação da adega autenticada. A empresa é
determinada exclusivamente pelo access token; parâmetros como `company_id` são ignorados.

Permissão: Bearer access token. Campos financeiros sensíveis respeitam
`can_view_reports`; contas a pagar respeitam `can_manage_payables`.

Conteúdo de `data`:

- data de referência;
- total e quantidade de vendas do dia;
- ticket médio e lucro, quando autorizados;
- status e identificação do caixa atual;
- totais por forma de pagamento, quando autorizados;
- cinco produtos mais vendidos;
- produtos abaixo do estoque mínimo;
- seis vendas recentes;
- contas vencidas ou com vencimento em até três dias, quando autorizadas.

As somas, agrupamentos e limites são calculados no backend para manter o cliente Windows
leve e evitar o envio de listas completas de vendas.

## Relatórios da API

### `GET /api/v1/reports/summary`

Descrição: retorna o resumo de relatórios da adega autenticada para o cliente Windows
nativo. A empresa é sempre definida pelo access token; o endpoint ignora qualquer tentativa
de trocar adega por parâmetro.

Permissão: Bearer access token com `can_view_reports`.

Parâmetros opcionais:

| Parâmetro | Valores | Função |
|---|---|---|
| `period` | `daily`, `weekly`, `monthly`, `annual`, `custom` | Define o intervalo principal. Padrão: `daily`. |
| `start_date` | `YYYY-MM-DD` | Data inicial usada quando `period=custom`. |
| `end_date` | `YYYY-MM-DD` | Data final usada quando `period=custom`. |
| `chart_metric` | `revenue`, `quantity` | Alterna o gráfico entre faturamento e quantidade. |

Conteúdo de `data`:

- período aplicado, rótulo, data inicial e data final;
- resumo com quantidade de vendas, itens vendidos, subtotal, desconto, total final, lucro e ticket médio;
- totais por forma de pagamento: Dinheiro, Pix, Débito e Crédito;
- ranking dos dez produtos mais vendidos no período;
- gráfico agregado por hora no diário, por dia em períodos semanais/mensais/customizados e por mês no anual;
- pico do gráfico atual, pico por quantidade e pico por faturamento.

Exemplo de resposta:

```json
{
  "success": true,
  "data": {
    "period": "daily",
    "period_label": "Diário",
    "start_date": "2026-07-17",
    "end_date": "2026-07-17",
    "chart_metric": "revenue",
    "summary": {
      "sales_count": 12,
      "items_count": 28,
      "subtotal": 1350.0,
      "discount": 50.0,
      "final": 1300.0,
      "profit": 420.0,
      "average_ticket": 108.33
    },
    "payment_totals": [
      {"method": "money", "label": "Dinheiro", "amount": 300.0},
      {"method": "pix", "label": "Pix", "amount": 500.0}
    ],
    "top_products": [],
    "chart": {
      "metric": "revenue",
      "metric_label": "Faturamento",
      "buckets": [],
      "peak": null,
      "peak_by_quantity": null,
      "peak_by_revenue": null
    }
  },
  "message": null,
  "errors": []
}
```

As agregações são calculadas no backend a partir de `sales`, `sale_items` e `payments`.
O cliente WPF apenas renderiza os cartões, ranking e gráfico, mantendo baixo consumo de
CPU e memória em computadores simples.

### `GET /api/v1/reports/products`

Descrição: retorna o relatório paginado de performance por produto da adega autenticada.
É o endpoint usado pelo cliente Windows nativo para mostrar produtos vendidos, produtos
sem venda e indicadores por item sem carregar todo o histórico no frontend.

Permissão: Bearer access token com `can_view_reports`.

Parâmetros opcionais:

| Parâmetro | Valores | Função |
|---|---|---|
| `period` | `daily`, `weekly`, `monthly`, `annual`, `custom` | Define o intervalo principal. Padrão: `daily`. |
| `start_date` | `YYYY-MM-DD` | Data inicial usada quando `period=custom`. |
| `end_date` | `YYYY-MM-DD` | Data final usada quando `period=custom`. |
| `q` | texto | Busca por produto, categoria ou código de barras. |
| `category_id` | inteiro | Limita o relatório a uma categoria da adega. |
| `product_id` | inteiro | Limita o relatório a um produto específico da adega. |
| `sort` | `quantity_desc`, `revenue_desc`, `profit_desc`, `stock_asc`, `no_sales` | Ordenação do resultado. |
| `page` | inteiro | Página solicitada. Padrão: `1`. |
| `per_page` | `1` a `100` | Tamanho da página. Padrão: `25`. |

Conteúdo de `data`:

- período aplicado, rótulo, data inicial e data final;
- filtros aplicados;
- resumo com quantidade de produtos, unidades vendidas, faturamento, custo, lucro e ticket médio;
- lista paginada com produto, categoria, quantidade vendida, faturamento, custo, lucro, ticket médio, estoque e status;
- metadados de paginação;
- opções de ordenação aceitas.

Exemplo de resposta:

```json
{
  "success": true,
  "data": {
    "period": "daily",
    "period_label": "Diário",
    "start_date": "2026-07-17",
    "end_date": "2026-07-17",
    "search": "",
    "category_id": 0,
    "product_id": 0,
    "summary": {
      "products": 8,
      "quantity": 32,
      "revenue": 1540.0,
      "cost": 900.0,
      "profit": 640.0,
      "average_ticket": 48.12
    },
    "items": [
      {
        "product_id": 10,
        "product_name": "Coca Cola 2L",
        "barcode": "7890000000000",
        "category_id": 3,
        "category_name": "Refrigerante",
        "quantity": 12,
        "revenue": 120.0,
        "cost": 72.0,
        "profit": 48.0,
        "average_ticket": 10.0,
        "stock": 90,
        "active": true
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 25,
      "total": 8,
      "pages": 1,
      "has_next": false,
      "has_prev": false
    },
    "sort": "quantity_desc",
    "sort_options": [
      {"value": "quantity_desc", "label": "Mais vendidos"}
    ]
  },
  "message": null,
  "errors": []
}
```

As agregações são feitas no backend a partir de `sale_items`, `sales`, `products` e
`categories`. A ordenação `no_sales` usa `LEFT JOIN` para incluir produtos ativos sem
venda no período, útil para identificar estoque parado.

## Caixa da API

Os endpoints de caixa exigem Bearer access token, transporte seguro e a permissão
`can_manage_cash_register`. A adega é sempre obtida do token. Valores financeiros são
retornados somente quando o usuário também possui `can_view_reports`.

### `GET /api/v1/cash-registers/summary`

Descrição: retorna o caixa aberto da adega e os dez caixas fechados mais recentes.

Cada registro contém identificação, status, abertura, fechamento, responsável e
quantidade de vendas. Quando autorizado, também inclui valor inicial, valor final, total
vendido, valor esperado, diferença e totais de Dinheiro, Pix, Débito e Crédito.

### `GET /api/v1/cash-registers/<cash_register_id>`

Descrição: retorna o detalhe de um caixa específico da adega autenticada.

A resposta inclui o mesmo registro financeiro do resumo, quando permitido, e uma linha
do tempo cronológica das vendas vinculadas ao caixa. Cada venda da linha do tempo traz
horário, vendedor, status, formas de pagamento, itens vendidos e pagamentos. Valores de
venda, itens e pagamentos são omitidos quando o usuário não possui `can_view_reports`.

Erros principais:

- `404 cash_register_not_found`: o caixa não existe ou pertence a outra adega;
- `403 permission_denied`: o usuário não possui permissão para caixa.

### `POST /api/v1/cash-registers/open`

Descrição: abre um caixa para a adega autenticada.

Payload:

```json
{
  "opening_amount": "150,00"
}
```

Resposta: o mesmo snapshot de `summary`, com o novo caixa em `current_register` e HTTP
`201`. A abertura bloqueia a empresa durante a transação para impedir dois caixas
simultâneos e registra o evento na auditoria.

Erros principais:

- `422 invalid_money`: valor ausente, inválido ou fora do limite;
- `409 cash_register_already_open`: já existe um caixa aberto.

### `POST /api/v1/cash-registers/close`

Descrição: fecha o caixa atual após conferir exatamente o valor inicial somado às vendas.

Payload:

```json
{
  "cash_register_id": 18,
  "closing_amount": "487,50"
}
```

O fechamento usa transação e bloqueio de linha. Se o caixa mudou desde a última consulta,
o cliente precisa atualizar o snapshot. Quando o valor não confere, o servidor não altera
o caixa e retorna HTTP `422`; usuários autorizados recebem o valor faltante ou excedente,
enquanto os demais recebem uma orientação sem revelar totais financeiros.

Erros principais:

- `422 invalid_integer`: identificador inválido;
- `422 invalid_money`: valor de fechamento inválido;
- `422 cash_register_amount_mismatch`: valor diferente do esperado;
- `409 cash_register_not_open`: não existe caixa aberto;
- `409 cash_register_changed`: o caixa aberto não corresponde ao identificador enviado.

## Vendas da API

### `POST /api/v1/sales`

Descrição: registra uma venda completa para a adega autenticada. Exige Bearer access
token, transporte seguro e a permissão `can_manage_sales`. A empresa e o usuário são
obtidos exclusivamente do token; o cliente não informa `company_id`.

O cabeçalho `Idempotency-Key` é obrigatório e precisa conter de 8 a 128 caracteres
alfanuméricos seguros. A mesma chave pode ser reenviada depois de timeout ou queda de
conexão: o servidor retorna a venda já gravada sem baixar o estoque novamente.

Payload:

```json
{
  "idempotency_key": "windows-7ea3b491a6e04ab3b822b1f9d6813790",
  "discount_amount": "2,00",
  "items": [
    {"product_id": 15, "quantity": 2}
  ],
  "payments": [
    {"method": "money", "amount": "10,00"},
    {"method": "pix", "amount": "12,00"}
  ]
}
```

Formas aceitas: `money`, `pix`, `debit` e `credit`. O servidor agrega itens repetidos,
valida produtos ativos, caixa aberto, kits, estoque, desconto e pagamentos. Em uma única
transação ele cria venda, itens e pagamentos, baixa o estoque, calcula lucro/taxas, grava
auditoria e associa a chave de idempotência.

A resposta usa HTTP `201` na primeira gravação e HTTP `200` ao recuperar uma tentativa
já processada. O campo `already_processed` informa qual caso ocorreu. O comprovante em
`data` inclui venda, caixa, subtotal, desconto, total, pago, troco, itens, pagamentos e
eventuais avisos de estoque negativo permitido.

Erros principais:

- `409 cash_register_required`: não existe caixa aberto;
- `404 product_not_found`: produto não pertence à adega autenticada;
- `409 product_inactive`: produto inativo;
- `409 kit_not_configured`: kit sem componente válido;
- `409 insufficient_stock`: estoque negativo bloqueado pela configuração da adega;
- `422 discount_exceeds_subtotal`: desconto maior que o subtotal;
- `422 payment_insufficient`: pagamentos não completam o total;
- `409 sale_request_conflict`: outra tentativa com a mesma chave ainda está em processamento.

### `POST /api/v1/sales/<sale_id>/cancel`

Descrição: cancela logicamente uma venda, devolve exatamente o estoque originalmente baixado
e mantém itens e pagamentos para auditoria. Exige `can_cancel_sales`.

Payload: `{"reason": "Cliente desistiu antes de retirar."}`. O motivo é obrigatório e aceita
até 500 caracteres. O retorno contém a venda atualizada, os movimentos de devolução e o campo
`cash_register_was_closed`. Repetir a operação retorna `409 sale_already_cancelled` sem nova
devolução. A referência completa está em `docs/27-cancelamento-estorno-vendas.md`.

## Estoque da API

Todos os endpoints de estoque exigem Bearer access token e transporte seguro. A empresa é
sempre determinada pelo token; o cliente Windows não envia `company_id` nem acessa o
MySQL diretamente.

### `GET /api/v1/stock/movements`

Descrição: consulta paginada do histórico de movimentações de estoque da adega.

Permissão exigida: `can_view_stock_movements`.

Query params:

- `q`: busca opcional por produto, motivo ou observação;
- `category_id`: categoria da própria adega;
- `movement_type`: `all`, `entry`, `sale`, `adjustment_in`, `adjustment_out`,
  `initial_stock`, `import` ou `return`;
- `source_type`: `all`, `manual`, `sale`, `product_create`, `product_edit`, `import` ou
  `system`;
- `page`: página positiva, padrão `1`;
- `per_page`: itens por página, padrão `25` e máximo `100`.

Resposta em `data`:

```json
{
  "items": [
    {
      "id": 20,
      "created_at": "2026-07-17T12:00:00Z",
      "product": {
        "id": 15,
        "name": "Coca Cola 2L",
        "category": {"id": 7, "name": "Refrigerantes"}
      },
      "user": {"id": 10, "username": "operador"},
      "movement_type": "entry",
      "movement_type_label": "Entrada",
      "source_type": "manual",
      "source_type_label": "Manual",
      "quantity": 5,
      "previous_stock": 8,
      "new_stock": 13,
      "unit_cost": 7.5,
      "total_cost": 37.5,
      "reason": "Compra de fornecedor",
      "notes": ""
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 25,
    "total": 1,
    "total_pages": 1
  },
  "summary": {
    "entries_quantity": 5,
    "exits_quantity": 0,
    "movement_count": 1,
    "product_count": 1
  },
  "movement_types": [],
  "source_types": []
}
```

O resumo é calculado no servidor usando os mesmos filtros da consulta, evitando que o
cliente precise carregar todo o histórico.

### `POST /api/v1/stock/entries`

Descrição: registra entrada manual de mercadoria e aumenta o saldo do produto.

Permissão exigida: `can_manage_stock`.

Payload:

```json
{
  "product_id": 15,
  "quantity": 5,
  "unit_cost": "7,50",
  "reason": "Compra de fornecedor",
  "notes": "Nota 123",
  "update_cost": true
}
```

Regras:

- o produto precisa pertencer à adega autenticada;
- `quantity` precisa ser maior que zero;
- `unit_cost` pode atualizar o custo atual do produto quando `update_cost` for `true`;
- a movimentação é gravada com `movement_type=entry` e `source_type=manual`;
- a operação usa o `stock_service`, atualiza o saldo e registra auditoria.

Resposta em `data`: movimentação criada, no mesmo formato de `GET /api/v1/stock/movements`.

### `POST /api/v1/stock/adjustments`

Descrição: ajusta manualmente o estoque para um saldo final ou aplica uma diferença de
entrada/saída.

Permissão exigida: `can_manage_stock`.

Payload por saldo final:

```json
{
  "product_id": 15,
  "adjustment_mode": "target",
  "target_stock": 20,
  "reason": "Inventário",
  "notes": ""
}
```

Payload por diferença:

```json
{
  "product_id": 15,
  "adjustment_mode": "delta",
  "direction": "out",
  "quantity": 2,
  "reason": "Quebra",
  "notes": ""
}
```

Regras:

- `adjustment_mode` aceita `target` ou `delta`;
- em modo `delta`, `direction` aceita `in` ou `out`;
- ajuste para o mesmo saldo retorna `changed=false`;
- estoque negativo respeita `allow_negative_stock` da adega;
- a movimentação usa `adjustment_in` ou `adjustment_out`, com origem `manual`.

Resposta em `data`:

```json
{
  "changed": true,
  "movement": {}
}
```

Erros principais:

- `404 product_not_found`: produto não pertence à adega autenticada;
- `422 invalid_adjustment_mode`: modo inválido;
- `422 invalid_adjustment_direction`: direção inválida;
- `422 stock_movement_error`: regra de estoque rejeitou a operação.

## Catálogo da API

Todos os endpoints de catálogo exigem Bearer access token, transporte seguro e a
permissão `can_view_products`. A empresa é obtida exclusivamente da identidade do token;
parâmetros enviados pelo cliente não podem trocar a adega consultada.

### `GET /api/v1/catalog/categories`

Descrição: lista as categorias da adega em ordem alfabética com a quantidade de produtos.

Query params:

- `q`: busca opcional por nome, limitada a 120 caracteres.

Resposta em `data`:

```json
{
  "items": [
    {
      "id": 7,
      "name": "Refrigerantes",
      "product_count": 12
    }
  ],
  "total": 1
}
```

### `POST /api/v1/catalog/categories`

Descrição: cria uma categoria na adega do usuário autenticado.

Permissão exigida: `can_manage_categories`.

Corpo JSON:

```json
{
  "name": "Refrigerantes"
}
```

Regras:

- `name` é obrigatório;
- o nome não pode duplicar outra categoria da mesma adega;
- adegas diferentes podem usar o mesmo nome;
- a criação gera evento de auditoria `category_created`.

Resposta em `data`: objeto de categoria com `id`, `name` e `product_count`.

### `PUT /api/v1/catalog/categories/<category_id>`

Descrição: atualiza o nome de uma categoria da adega do usuário autenticado.

Permissão exigida: `can_manage_categories`.

Corpo JSON:

```json
{
  "name": "Cervejas"
}
```

Regras:

- a categoria precisa pertencer à adega do token;
- o nome não pode duplicar outra categoria da mesma adega;
- a edição gera evento de auditoria `category_updated` quando houver alteração.

Resposta em `data`: categoria atualizada com a contagem atual de produtos.

### `DELETE /api/v1/catalog/categories/<category_id>`

Descrição: exclui uma categoria vazia da adega do usuário autenticado.

Permissão exigida: `can_manage_categories`.

Regras:

- a categoria precisa pertencer à adega do token;
- categorias com produtos vinculados retornam `409 category_has_products`;
- a exclusão gera evento de auditoria `category_deleted`.

Resposta em `data`:

```json
{
  "id": 7,
  "deleted": true
}
```

### `GET /api/v1/catalog/products`

Descrição: consulta paginada e somente leitura dos produtos da adega.

Query params:

- `q`: nome ou código de barras;
- `category_id`: categoria da própria adega;
- `active`: `all`, `active` ou `inactive`;
- `sort`: `name`, `name_desc`, `price`, `price_desc`, `stock` ou `stock_desc`;
- `page`: página positiva, padrão `1`;
- `per_page`: itens por página, padrão `30` e máximo `100`.

A resposta contém nome, código, categoria, preço de venda, estoque efetivo, estoque
mínimo, status e indicação de kit. Custo e lucro só são incluídos quando o usuário possui
`can_manage_products`.

```json
{
  "items": [
    {
      "id": 15,
      "name": "Coca Cola 2L",
      "barcode": "7890002",
      "category": {"id": 7, "name": "Refrigerantes"},
      "sale_price": 12.0,
      "stock_quantity": 8,
      "min_stock_quantity": 2,
      "active": true,
      "is_kit": false
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 30,
    "total": 1,
    "total_pages": 1
  }
}
```

### `POST /api/v1/catalog/products`

Descrição: cria um produto na adega do usuário autenticado.

Permissão exigida: `can_manage_products`.

Corpo JSON:

```json
{
  "name": "Coca Cola 2L",
  "barcode": "7890002",
  "category_id": 7,
  "cost_price": 7.5,
  "sale_price": 12.0,
  "stock_quantity": 8,
  "min_stock_quantity": 2,
  "active": true,
  "stock_reason": "Cadastro inicial"
}
```

Regras:

- `name` é obrigatório;
- `category_id`, quando informado, precisa pertencer à adega do token;
- `barcode` não pode duplicar outro produto da mesma adega;
- custo e venda não podem ser negativos;
- estoque mínimo não pode ser negativo;
- o estoque inicial é registrado como movimentação quando diferente de zero;
- a criação gera evento de auditoria `product_created`.

Resposta em `data`: objeto de produto no mesmo formato de `GET /api/v1/catalog/products`,
incluindo custo e lucro.

### `PUT /api/v1/catalog/products/<product_id>`

Descrição: atualiza um produto existente da adega do usuário autenticado.

Permissão exigida: `can_manage_products`.

Corpo JSON: mesmo formato de `POST /api/v1/catalog/products`.

Regras:

- o produto precisa pertencer à adega do token;
- `category_id`, quando informado, precisa pertencer à mesma adega;
- `barcode` não pode duplicar outro produto da mesma adega;
- alteração de estoque cria movimentação com origem `product_edit`;
- a edição gera evento de auditoria `product_updated`, com valores alterados.

Resposta em `data`: produto atualizado no mesmo formato de catálogo.

## Autenticação

### `GET /login`

Descrição: exibe tela de login/cadastro.

Permissão: pública.

Resposta: HTML `login.html`.

### `POST /login`

Descrição: autentica usuário ou cadastra usuário, dependendo de `form_type`.

Permissão: pública.

Payload login:

```json
{
  "form_type": "login",
  "username": "admin",
  "password": "SenhaForte123"
}
```

Payload cadastro:

```json
{
  "form_type": "register",
  "username": "operador",
  "email": "operador@example.com",
  "password": "SenhaForte123",
  "confirm_password": "SenhaForte123"
}
```

Sucesso: redirect para `/dashboard`.

Erros:

- Usuário/e-mail ou senha inválidos.
- Usuário obrigatório.
- Senha fora da política mínima.
- Confirmação divergente.
- Usuário duplicado.

### `POST /logout`

Descrição: encerra sessão.

Permissão: autenticado.

Sucesso: redirect para `/login`.

Observação: `GET /logout` não altera sessão e retorna método não permitido.

## Configurações

### `GET /api/v1/settings/account`

Descrição: retorna os dados de perfil e permissões do usuário autenticado para o cliente Windows.

Permissão: autenticado via bearer token.

Resposta:

```json
{
  "data": {
    "user": {
      "id": 2,
      "username": "adegajf",
      "first_name": "Adega",
      "last_name": "JF",
      "email": "contato@example.com",
      "phone": "(11) 99999-0000",
      "role": "admin",
      "company_id": 4,
      "company_name": "Adega JF",
      "permissions": {
        "can_manage_sales": true,
        "can_manage_cash_register": true,
        "can_view_reports": true
      }
    }
  }
}
```

### `PUT /api/v1/settings/profile`

Descrição: atualiza nome, sobrenome e telefone do usuário autenticado.

Permissão: autenticado via bearer token.

Payload:

```json
{
  "first_name": "Rafael",
  "last_name": "Borges",
  "phone": "(11) 99999-0000"
}
```

Regras:

- nome e sobrenome são normalizados com espaços extras removidos;
- telefone é opcional;
- o retorno já devolve a identidade atualizada para o cliente atualizar a sessão local.

### `PUT /api/v1/settings/company`

Descrição: atualiza regras operacionais da adega pelo cliente Windows.

Permissão: usuário `admin`, `manager`, `master` ou com permissão de gerenciar configurações.

Payload:

```json
{
  "allow_negative_stock": true,
  "pix_fee_enabled": true,
  "pix_fee_percent": "1,25",
  "debit_fee_enabled": true,
  "debit_fee_percent": "2.50",
  "credit_fee_enabled": false,
  "credit_fee_percent": "0"
}
```

Regras:

- a alteração é sempre aplicada na adega do token;
- `allow_negative_stock` controla se a venda pode baixar o estoque para negativo;
- os percentuais de Pix, débito e crédito aceitam vírgula ou ponto decimal;
- percentuais acima de `100` retornam `invalid_percent`;
- usuários sem permissão administrativa recebem `permission_denied`;
- a alteração gera auditoria `company_settings_updated`;
- o retorno devolve o mesmo snapshot de `/api/v1/settings/account`, já com as novas regras.

### `PUT /api/v1/settings/password`

Descrição: altera a senha do usuário autenticado.

Permissão: autenticado via bearer token.

Payload:

```json
{
  "current_password": "SenhaAtual123",
  "new_password": "NovaSenha123",
  "confirm_password": "NovaSenha123"
}
```

Regras:

- senha atual precisa estar correta;
- nova senha precisa ter pelo menos 6 caracteres;
- confirmação precisa bater;
- depois da alteração, as sessões API antigas do usuário são revogadas.

### `PUT /api/v1/settings/backup`

Descrição: atualiza a frequência de backup da adega pelo cliente Windows.

Permissão: usuário `admin`, `manager`, `master` ou com permissão de gerenciar configurações.

Payload:

```json
{
  "backup_frequency": "weekly"
}
```

Valores aceitos:

- `manual`: somente manual;
- `daily`: diário;
- `weekly`: semanal;
- `monthly`: mensal.

Regras:

- a alteração é sempre aplicada na adega do token;
- frequências inválidas retornam `invalid_backup_frequency`;
- a alteração gera auditoria `backup_settings_updated`.

### `POST /api/v1/settings/backup/run`

Descrição: gera um backup manual da adega atual pelo cliente Windows.

Permissão: usuário `admin`, `manager`, `master` ou com permissão de gerenciar configurações.

Payload: objeto JSON vazio.

Sucesso:

```json
{
  "data": {
    "company_settings": {
      "backup_frequency": "weekly",
      "backup_last_status": "success"
    },
    "backup": {
      "file_name": "adega_4_20260719_120000_windows_manual.sql",
      "status": "success",
      "generated_at": "2026-07-19T12:00:00"
    }
  }
}
```

Regras:

- o backup usa o mesmo mecanismo da versão web;
- o arquivo é criado na pasta de backups configurada no servidor;
- a operação gera auditoria `backup_created`;
- falhas retornam `backup_failed` e são registradas nos logs do servidor.

### `GET /api/v1/settings/export/<tipo>`

Descrição: exporta dados da adega atual em CSV para o cliente Windows nativo.

Permissão: usuário `admin` ou `master` da adega autenticada.

Tipos aceitos:

- `produtos`;
- `vendas`;
- `caixas`;
- `contas`.

Resposta: arquivo `text/csv; charset=utf-8`, com BOM UTF-8, separador `;` e cabeçalho
`Content-Disposition` sugerindo um nome como `girofy_produtos_20260719_120000.csv`.

Regras:

- a exportação é sempre feita dentro da adega do token;
- o cliente não envia `company_id` nem acessa banco diretamente;
- funcionários comuns e gerentes sem perfil administrativo recebem `permission_denied`;
- tipo inválido retorna `invalid_export_type`;
- a operação gera auditoria `data_exported`;
- a resposta recebe `Cache-Control: no-store`.

### `POST /api/v1/settings/import/products`

Descrição: importa produtos da adega atual a partir de uma planilha enviada pelo cliente
Windows nativo.

Permissão: usuário `admin`, `manager` ou `master` da adega autenticada.

Content-Type: `multipart/form-data`.

Campo aceito:

- `spreadsheet`: arquivo `.csv` ou `.xlsx`;
- `file`: alias aceito para compatibilidade.

Colunas reconhecidas:

- `produto`, `nome`, `nome_produto`, `product`, `name`;
- `categoria`, `category`;
- `codigo`, `código`, `codigo de barras`, `código de barras`, `barcode`;
- `valor de custo`, `custo`, `preço de custo`, `cost_price`, `cost`;
- `valor de venda`, `venda`, `preço de venda`, `sale_price`, `price`;
- `estoque atual`, `estoque_atual`, `estoque`, `stock_quantity`, `stock`;
- `estoque mínimo`, `estoque_minimo`, `min_stock_quantity`, `min_stock`.

Sucesso:

```json
{
  "data": {
    "created": 12,
    "updated": 3,
    "skipped": 1,
    "movements": 12,
    "total_rows": 16
  }
}
```

Regras:

- a importação é sempre feita dentro da adega do token;
- categorias inexistentes são criadas na própria adega;
- produto existente é localizado primeiro por código de barras e depois por nome;
- produto novo é criado ativo;
- linhas sem nome de produto são ignoradas;
- estoque inicial ou alterado gera movimentação de estoque;
- produtos criados/atualizados geram auditoria;
- funcionários comuns recebem `permission_denied`;
- arquivo ausente retorna `file_required`;
- extensão inválida retorna `invalid_import_file`;
- falha de leitura ou conteúdo inválido retorna `invalid_import_data`;
- falha inesperada retorna `import_failed` e é registrada nos logs do servidor.

### `GET /api/v1/settings/team`

Descrição: lista funcionários da adega atual para a tela nativa de equipe.

Permissão: usuário `admin`, `manager`, `master` ou com permissão de gerenciar configurações.

Query params:

- `search`: busca opcional por usuário, nome, sobrenome, email ou CPF.

Resposta:

```json
{
  "data": {
    "employees": [
      {
        "id": 7,
        "username": "joao",
        "first_name": "João",
        "last_name": "Silva",
        "cpf": "12345678900",
        "email": "joao@example.com",
        "phone": "(11) 90000-0000",
        "role": "operator",
        "role_label": "Funcionário",
        "is_active": true,
        "is_current_user": false,
        "permissions": {
          "can_manage_sales": true,
          "can_manage_cash_register": true
        }
      }
    ],
    "roles": [
      {"value": "operator", "label": "Funcionário"},
      {"value": "manager", "label": "Gerente"},
      {"value": "admin", "label": "Admin"}
    ],
    "permissions": []
  }
}
```

### `POST /api/v1/settings/team`

Descrição: cadastra um funcionário na adega atual.

Permissão: usuário `admin`, `manager`, `master` ou com permissão de gerenciar configurações.

Payload:

```json
{
  "username": "joao",
  "password": "Senha123",
  "first_name": "João",
  "last_name": "Silva",
  "cpf": "12345678900",
  "email": "joao@example.com",
  "phone": "(11) 90000-0000",
  "role": "operator",
  "is_active": true
}
```

Regras:

- usuário é obrigatório e precisa ser único no sistema;
- senha precisa ter pelo menos 6 caracteres;
- CPF, quando informado, precisa ser único dentro da mesma adega;
- email, quando informado, precisa ter formato válido;
- perfis aceitos: `operator`, `manager`, `admin`;
- permissões padrão são aplicadas automaticamente conforme o perfil;
- o usuário criado já fica com email marcado como verificado para uso interno da equipe.

### `PUT /api/v1/settings/team/<user_id>`

Descrição: atualiza um funcionário da adega atual.

Permissão: usuário `admin`, `manager`, `master` ou com permissão de gerenciar configurações.

Payload:

```json
{
  "first_name": "João",
  "last_name": "Silva",
  "cpf": "12345678900",
  "email": "joao@example.com",
  "phone": "(11) 90000-0000",
  "role": "manager",
  "is_active": true
}
```

Regras:

- só atualiza usuários da adega atual;
- CPF continua único dentro da adega;
- o usuário autenticado não pode se inativar nem se rebaixar pela própria tela;
- alterar perfil reaplica as permissões padrão daquele perfil.

### `GET /configuracoes`

Descrição: exibe tela de configurações.

Permissão: autenticado.

### `POST /configuracoes`

Descrição: atualiza perfil, email ou senha.

Permissão: autenticado.

Payload perfil:

```json
{
  "form_type": "profile",
  "first_name": "Rafael",
  "last_name": "Borges",
  "phone": "(11) 99999-0000"
}
```

Payload email:

```json
{
  "form_type": "email",
  "email": "rafael@example.com"
}
```

Payload senha:

```json
{
  "form_type": "password",
  "current_password": "SenhaForte123",
  "new_password": "NovaSenhaForte123",
  "confirm_password": "NovaSenhaForte123"
}
```

## Produtos

### `GET /catalogo/produtos`

Descrição: lista produtos.

Permissão: autenticado.

Query params:

- `q`: busca por nome ou código.
- `status`: `active`, `inactive`, `all`.
- `category_id`: ID da categoria.
- `stock`: `all`, `available`, `low`, `out`.
- `min_price`: preço mínimo.
- `max_price`: preço máximo.
- `sort`: `name_asc`, `name_desc`, `price_asc`, `price_desc`, `stock_asc`, `stock_desc`, `created_desc`.

Resposta: HTML `catalog/products.html`.

### `GET /catalogo/produtos/novo`

Descrição: exibe formulário de novo produto.

Permissão: autenticado.

### `POST /catalogo/produtos/novo`

Descrição: cria produto.

Permissão: autenticado.

Payload:

```json
{
  "name": "Vinho Tinto",
  "barcode": "789000000001",
  "category_id": "1",
  "cost_price": "25,50",
  "sale_price": "39,90",
  "stock_quantity": "12",
  "active": "on",
  "is_kit": "on",
  "kit_component_product_id": "2",
  "kit_component_quantity": "8",
  "stock_reason": "Estoque inicial"
}
```

Erros:

- Nome ausente.
- Código de barras duplicado.
- Kit sem produto base ou quantidade.
- Kit apontando para si mesmo.

### `GET /catalogo/produtos/<product_id>/editar`

Descrição: exibe edição de produto.

Permissão: autenticado.

### `POST /catalogo/produtos/<product_id>/editar`

Descrição: atualiza produto.

Permissão: autenticado.

Payload: mesmos campos de criação.

Observação: se `stock_quantity` mudar, o backend gera uma movimentação de estoque.

### `POST /catalogo/produtos/<product_id>/atualizar`

Descrição: edição rápida do produto pela listagem.

Permissão: autenticado.

### `POST /catalogo/produtos/<product_id>/alternar-status`

Descrição: ativa ou inativa produto.

Permissão: autenticado.

### `POST /catalogo/produtos/<product_id>/excluir`

Descrição: exclui produto fisicamente.

Permissão: autenticado.

## Categorias

### `GET /catalogo/categorias`

Descrição: lista categorias.

Permissão: autenticado.

Query params:

- `q`: busca.
- `usage`: `all`, `with_products`, `empty`.
- `sort`: `name_asc`, `name_desc`, `products_desc`, `products_asc`, `created_desc`.

### `POST /catalogo/categorias`

Descrição: cria categoria.

Permissão: autenticado.

Payload:

```json
{
  "name": "Bebidas"
}
```

Erros:

- Nome ausente.
- Nome duplicado.

### `POST /catalogo/categorias/<category_id>/atualizar`

Descrição: atualiza categoria.

Permissão: autenticado.

### `POST /catalogo/categorias/<category_id>/excluir`

Descrição: exclui categoria se não houver produtos vinculados.

Permissão: autenticado.

## Dashboard

### `GET /`

Descrição: redireciona/renderiza dashboard pela mesma função de `/dashboard`.

Permissão: autenticado.

### `GET /dashboard`

Descrição: tela inicial.

Permissão: autenticado.

## Vendas

### `GET /vendas`

Descrição: lista o histórico de vendas do dia atual da adega logada.

Permissão: autenticado.

### `GET /vendas/nova`

Descrição: exibe formulário de venda se houver caixa aberto; caso contrário redireciona para caixa.

Permissão: autenticado.

### `POST /vendas/nova`

Descrição: finaliza venda.

Permissão: autenticado.

Payload:

```json
{
  "product_id[]": ["1", "2"],
  "quantity[]": ["2", "3"],
  "discount_amount": "10,00",
  "payment_money": "50,00",
  "payment_pix": "54,00",
  "payment_debit": "",
  "payment_credit": ""
}
```

Erros:

- Caixa fechado.
- Nenhum produto válido.
- Produto inativo/inexistente.
- Kit sem configuração.
- Estoque insuficiente, somente quando a adega estiver configurada para bloquear venda sem saldo.
- Pagamento insuficiente.

Observação: cada item finalizado gera movimentação de estoque `sale` na mesma transação
da venda. Produto kit movimenta o componente base.

### `GET /vendas/<sale_id>`

Descrição: detalhe da venda.

Permissão: autenticado.

## Estoque

### `GET /estoque/movimentacoes`

Descrição: lista histórico de movimentações de estoque da adega atual.

Permissão: `can_view_stock_movements`.

Query params:

- `q`: busca por produto.
- `category_id`: categoria.
- `movement_type`: tipo técnico da movimentação.
- `user_id`: usuário responsável.
- `start_date`: data inicial.
- `end_date`: data final.
- `page`: página.

Resposta: HTML `stock/movements.html`.

### `GET /estoque/entrada`

Descrição: exibe formulário de entrada manual.

Permissão: `can_manage_stock`.

### `POST /estoque/entrada`

Descrição: registra entrada manual e cria `stock_movements`.

Permissão: `can_manage_stock`.

Payload:

```json
{
  "product_id": "1",
  "quantity": "12",
  "unit_cost": "8,50",
  "reason": "Compra de mercadoria",
  "notes": "Nota 123",
  "update_cost": "on"
}
```

### `GET /estoque/ajuste`

Descrição: exibe formulário de ajuste.

Permissão: `can_manage_stock`.

### `POST /estoque/ajuste`

Descrição: ajusta saldo por diferença ou saldo final e cria movimentação.

Permissão: `can_manage_stock`.

Payload por diferença:

```json
{
  "product_id": "1",
  "adjust_mode": "delta",
  "direction": "out",
  "quantity": "2",
  "reason": "Quebra"
}
```

Payload por saldo final:

```json
{
  "product_id": "1",
  "adjust_mode": "target",
  "new_stock": "20",
  "reason": "Inventário"
}
```

Erros:

- Produto inválido.
- Quantidade inválida.
- Motivo ausente.
- Saldo negativo quando a adega bloqueia estoque negativo.

## Auditoria

### `GET /auditoria`

Descrição: lista eventos de auditoria da adega atual.

Permissão: `can_view_audit_logs`.

Query params:

- `q`: busca textual.
- `user_id`: usuário.
- `action`: ação.
- `entity_type`: entidade.
- `method`: método HTTP.
- `start_date`: data inicial.
- `end_date`: data final.
- `page`: página.

Resposta: HTML `audit/index.html`.

### `GET /master/auditoria`

Descrição: lista auditoria central para o master do sistema.

Permissão: usuário `master`.

## Caixa

### `GET /caixa`

Descrição: exibe caixa atual e últimos caixas fechados.

Permissão: autenticado.

### `POST /caixa/abrir`

Descrição: abre caixa.

Permissão: autenticado.

Payload:

```json
{
  "opening_amount": "100,00"
}
```

Erro:

- Já existe caixa aberto.

### `POST /caixa/fechar`

Descrição: fecha caixa.

Permissão: autenticado.

Payload:

```json
{
  "closing_amount": "150,00"
}
```

Erros:

- Não há caixa aberto.
- Valor menor que esperado.
- Valor maior que esperado.

## Relatórios

### `GET /relatorios`

Descrição: relatório de vendas por período.

Permissão: autenticado.

Query params:

- `period`: `daily`, `weekly`, `monthly`, `annual`, `custom`.
- `start_date`: `YYYY-MM-DD`.
- `end_date`: `YYYY-MM-DD`.

Resposta: HTML `reports/index.html`.
### `POST /api/v1/auth/password-recovery/request`

`POST /api/v1/auth/password-recovery/request` é público e recebe:

```json
{
  "identifier": "usuario-ou-email"
}
```

O campo é aparado somente nas extremidades e aceita usuário ou e-mail. Campo vazio
retorna `422`; uma solicitação válida retorna sempre a mesma confirmação técnica,
inclusive quando não existe conta elegível. A resposta nunca contém usuário, e-mail,
empresa, token ou URL de redefinição.

Quando existe uma conta ativa, com e-mail confirmado e utilizável, o backend reutiliza o
mesmo serviço do fluxo web, invalida solicitações anteriores, gera um token com expiração
de 30 minutos e envia o link web `/reset-password/<token>`. O aplicativo Windows não
recebe nem processa esse token.

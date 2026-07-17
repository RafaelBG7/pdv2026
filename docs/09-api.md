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

## Caixa da API

Os endpoints de caixa exigem Bearer access token, transporte seguro e a permissão
`can_manage_cash_register`. A adega é sempre obtida do token. Valores financeiros são
retornados somente quando o usuário também possui `can_view_reports`.

### `GET /api/v1/cash-registers/summary`

Descrição: retorna o caixa aberto da adega e os dez caixas fechados mais recentes.

Cada registro contém identificação, status, abertura, fechamento, responsável e
quantidade de vendas. Quando autorizado, também inclui valor inicial, valor final, total
vendido, valor esperado, diferença e totais de Dinheiro, Pix, Débito e Crédito.

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

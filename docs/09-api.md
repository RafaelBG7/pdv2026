# 09 - Rotas HTTP

## Nota Importante

O projeto não implementa API REST/JSON pública. As rotas atuais são rotas web HTML, com renderização Jinja2 e submissão de formulários.

Esta documentação descreve os endpoints HTTP atuais.

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
  "password": "admin123"
}
```

Payload cadastro:

```json
{
  "form_type": "register",
  "username": "operador",
  "email": "operador@example.com",
  "password": "senha123",
  "confirm_password": "senha123"
}
```

Sucesso: redirect para `/dashboard`.

Erros:

- Usuário ou senha inválidos.
- Usuário obrigatório.
- Senha menor que 6 caracteres.
- Confirmação divergente.
- Usuário duplicado.

### `GET /logout`

Descrição: encerra sessão.

Permissão: autenticado.

Sucesso: redirect para `/login`.

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
  "current_password": "admin123",
  "new_password": "nova123",
  "confirm_password": "nova123"
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

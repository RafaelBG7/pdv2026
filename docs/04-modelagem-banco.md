# 04 - Modelagem do Banco

## Visão Geral

O sistema usa MySQL em dois níveis:

- Banco central: empresas, usuários, keys e dados administrativos.
- Banco por adega: categorias, produtos, vendas, pagamentos, caixa e contas a pagar.

ORM:

- Flask-SQLAlchemy / SQLAlchemy.

Criação e compatibilidade:

- `db.create_all()` cria tabelas do banco central.
- `tenant.py` cria bancos/tabelas das adegas.
- Funções em `app/__init__.py` garantem colunas adicionadas durante a evolução do projeto.

```mermaid
erDiagram
    COMPANIES ||--o{ USERS : has
    ACTIVATION_KEYS }o--o| COMPANIES : used_by
    USERS ||--o{ EMAIL_VERIFICATION_CODES : confirms
    USERS ||--o{ PASSWORD_RESET_TOKENS : resets
    USERS ||--o{ EMAIL_CHANGE_REQUESTS : changes_email
    COMPANIES ||--o{ EMAIL_ALERT_SETTINGS : configures
    COMPANIES ||--o{ EMAIL_ALERT_DELIVERIES : sends
    COMPANIES ||--o{ CATEGORIES : owns
    COMPANIES ||--o{ PRODUCTS : owns
    COMPANIES ||--o{ CASH_REGISTERS : owns
    COMPANIES ||--o{ SALES : owns
    COMPANIES ||--o{ PAYABLES : owns
    CATEGORIES ||--o{ PRODUCTS : groups
    PRODUCTS ||--o{ SALE_ITEMS : sold_as
    PRODUCTS ||--o{ PRODUCTS : kit_base
    CASH_REGISTERS ||--o{ SALES : contains
    SALES ||--o{ SALE_ITEMS : has
    SALES ||--o{ PAYMENTS : paid_by
```

## Banco Central

### `companies`

Representa cada adega/empresa.

Campos principais:

- `id`
- `name`
- `database_path`
- `active`
- `allow_negative_stock`
- `subscription_plan`
- `billing_cycle`
- `subscription_started_at`
- `subscription_renews_at`
- `activation_key`
- `activation_key_updated_at`
- `pix_fee_enabled`, `debit_fee_enabled`, `credit_fee_enabled`
- `pix_fee_percent`, `debit_fee_percent`, `credit_fee_percent`
- `backup_frequency`
- `backup_last_at`
- `backup_last_path`
- `backup_last_status`
- `created_at`

`allow_negative_stock` define por adega se a venda pode baixar o saldo abaixo de zero. Quando desativado, o comportamento permanece bloqueante.

### `users`

Representa usuários autenticáveis do sistema.

Campos principais:

- `id`
- `username`
- `first_name`
- `last_name`
- `cpf`
- `email`
- `email_verified`
- `email_verified_at`
- `phone`
- `password_hash`
- `role`
- `company_id`
- `is_active`
- `can_view_products`
- `can_manage_products`
- `can_manage_categories`
- `can_manage_sales`
- `can_manage_cash_register`
- `can_view_reports`
- `can_manage_payables`
- `can_manage_settings`
- `created_at`

Perfis atuais:

- `master`
- `admin`
- `manager`
- `operator`

### `activation_keys`

Representa keys geradas pelo master.

Campos principais:

- `id`
- `key`
- `plan`
- `renews_at`
- `active`
- `used_by_company_id`
- `used_at`
- `created_at`

### `email_verification_codes`

Representa códigos temporários para confirmar e-mail no cadastro.

Campos principais:

- `id`
- `user_id`
- `code_hash`
- `expires_at`
- `used`
- `attempts`
- `created_at`

### `password_reset_tokens`

Representa tokens temporários para redefinição de senha.

Campos principais:

- `id`
- `user_id`
- `token_hash`
- `expires_at`
- `used`
- `created_at`

### `email_change_requests`

Representa solicitações temporárias para trocar e-mail confirmando pelo e-mail antigo.

Campos principais:

- `id`
- `user_id`
- `old_email`
- `new_email`
- `token_hash`
- `expires_at`
- `used`
- `created_at`
- `confirmed_at`

### `email_alert_settings`

Representa a configuração de alertas críticos por e-mail por adega.

Campos principais:

- `id`
- `company_id`
- `alert_type`
- `enabled`
- `recipients`
- `created_at`
- `updated_at`

### `email_alert_deliveries`

Representa alertas por e-mail já enviados, evitando repetição do mesmo alerta.

Campos principais:

- `id`
- `company_id`
- `alert_type`
- `alert_key`
- `recipients`
- `sent_at`

## Banco da Adega

Cada adega possui as tabelas operacionais abaixo em seu próprio banco.

### `categories`

- `id`
- `name`
- `company_id`
- `created_at`

Regra: o nome é único dentro da adega, não globalmente entre todas as adegas.

### `products`

- `id`
- `name`
- `barcode`
- `category_id`
- `company_id`
- `cost_price`
- `sale_price`
- `stock_quantity`
- `min_stock_quantity`
- `active`
- `is_kit`
- `kit_component_product_id`
- `kit_component_quantity`
- `created_at`

Regras:

- Código de barras não pode duplicar dentro da adega.
- Kit baixa estoque do produto base.
- Estoque mínimo gera notificação.

### `cash_registers`

- `id`
- `opened_at`
- `closed_at`
- `opening_amount`
- `closing_amount`
- `status`
- `user_id`
- `company_id`

### `sales`

- `id`
- `created_at`
- `total_amount`
- `discount_amount`
- `final_amount`
- `payment_status`
- `user_id`
- `company_id`
- `cash_register_id`

### `sale_items`

- `id`
- `sale_id`
- `product_id`
- `quantity`
- `unit_price`
- `unit_cost_price`
- `total_price`
- `profit_amount`

### `payments`

- `id`
- `sale_id`
- `method`
- `amount`

Métodos:

- `money`
- `pix`
- `debit`
- `credit`

### `payables`

- `id`
- `company_id`
- `description`
- `category`
- `amount`
- `due_date`
- `paid`
- `paid_at`
- `notes`
- `created_at`

## Tabelas Ainda Não Existentes

- `stock_movements`: histórico de movimentação de estoque.
- `audit_logs`: auditoria de ações de negócio.
- `customers`: clientes.
- `suppliers`: fornecedores.
- `purchases`: compras/entrada de mercadoria.

## Observações Importantes

- `database_path` em `companies` guarda o nome do banco MySQL da adega.
- O campo `company_id` também existe em tabelas operacionais para reforçar vínculo lógico.
- A separação principal entre adegas é feita pelo banco selecionado em `tenant_session`.
- O projeto ainda não usa Alembic; mudanças de schema são aplicadas por compatibilidade no start da aplicação.

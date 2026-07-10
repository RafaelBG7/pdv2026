# 19 - Diagrama de Classe

## Diagrama Mermaid

```mermaid
classDiagram
    class Company {
        +Integer id
        +String name
        +String database_path
        +Boolean active
        +String subscription_plan
        +String billing_cycle
        +Date subscription_started_at
        +Date subscription_renews_at
        +String activation_key
        +Boolean pix_fee_enabled
        +Boolean debit_fee_enabled
        +Boolean credit_fee_enabled
        +Float pix_fee_percent
        +Float debit_fee_percent
        +Float credit_fee_percent
        +String backup_frequency
        +DateTime backup_last_at
        +String backup_last_path
        +String backup_last_status
        +subscription_expired
        +subscription_valid
    }

    class ActivationKey {
        +Integer id
        +String key
        +String plan
        +Date renews_at
        +Boolean active
        +Integer used_by_company_id
        +DateTime used_at
        +DateTime created_at
    }

    class User {
        +Integer id
        +String username
        +String first_name
        +String last_name
        +String cpf
        +String email
        +Boolean email_verified
        +DateTime email_verified_at
        +String phone
        +String password_hash
        +String role
        +Integer company_id
        +Boolean is_active
        +Boolean can_view_products
        +Boolean can_manage_products
        +Boolean can_manage_categories
        +Boolean can_manage_sales
        +Boolean can_manage_cash_register
        +Boolean can_view_reports
        +Boolean can_manage_payables
        +Boolean can_manage_settings
        +Boolean can_view_stock_movements
        +Boolean can_manage_stock
        +Boolean can_view_audit_logs
        +set_password(password)
        +check_password(password)
        +has_permission(permission)
        +role_label
    }

    class EmailVerificationCode {
        +Integer id
        +Integer user_id
        +String code_hash
        +DateTime expires_at
        +Boolean used
        +Integer attempts
        +DateTime created_at
    }

    class PasswordResetToken {
        +Integer id
        +Integer user_id
        +String token_hash
        +DateTime expires_at
        +Boolean used
        +DateTime created_at
    }

    class EmailChangeRequest {
        +Integer id
        +Integer user_id
        +String old_email
        +String new_email
        +String token_hash
        +DateTime expires_at
        +Boolean used
        +DateTime confirmed_at
    }

    class EmailAlertSetting {
        +Integer id
        +Integer company_id
        +String alert_type
        +Boolean enabled
        +Text recipients
        +recipient_list
    }

    class EmailAlertDelivery {
        +Integer id
        +Integer company_id
        +String alert_type
        +String alert_key
        +Text recipients
        +DateTime sent_at
    }

    class Category {
        +Integer id
        +String name
        +Integer company_id
        +DateTime created_at
    }

    class Product {
        +Integer id
        +String name
        +String barcode
        +Integer category_id
        +Integer company_id
        +Float cost_price
        +Float sale_price
        +Integer stock_quantity
        +Integer min_stock_quantity
        +Boolean active
        +Boolean is_kit
        +Integer kit_component_product_id
        +Integer kit_component_quantity
        +effective_stock_quantity
        +profit_amount
        +profit_margin_percent
    }

    class CashRegister {
        +Integer id
        +DateTime opened_at
        +DateTime closed_at
        +Float opening_amount
        +Float closing_amount
        +String status
        +Integer user_id
        +Integer company_id
    }

    class Sale {
        +Integer id
        +DateTime created_at
        +Float total_amount
        +Float discount_amount
        +Float final_amount
        +String payment_status
        +Integer user_id
        +Integer company_id
        +Integer cash_register_id
    }

    class SaleItem {
        +Integer id
        +Integer sale_id
        +Integer product_id
        +Integer quantity
        +Float unit_price
        +Float unit_cost_price
        +Float total_price
        +Float profit_amount
    }

    class Payment {
        +Integer id
        +Integer sale_id
        +String method
        +Float amount
    }

    class Payable {
        +Integer id
        +Integer company_id
        +String description
        +String category
        +Float amount
        +Date due_date
        +Boolean paid
        +DateTime paid_at
        +String notes
    }

    class StockMovement {
        +Integer id
        +Integer company_id
        +Integer product_id
        +Integer user_id
        +String movement_type
        +String source_type
        +Integer source_id
        +Integer quantity
        +Integer previous_stock
        +Integer new_stock
        +Float unit_cost
        +Float total_cost
        +String reason
        +Text notes
        +DateTime created_at
    }

    class AuditLog {
        +Integer id
        +Integer company_id
        +Integer user_id
        +String user_name
        +String user_role
        +String action
        +String entity_type
        +Integer entity_id
        +Text description
        +Text old_values
        +Text new_values
        +String ip_address
        +String user_agent
        +String request_id
        +String route
        +String http_method
        +DateTime created_at
    }

    Company "1" --> "0..*" User : users
    Company "1" --> "0..*" ActivationKey : used_keys
    User "1" --> "0..*" EmailVerificationCode : verification_codes
    User "1" --> "0..*" PasswordResetToken : reset_tokens
    User "1" --> "0..*" EmailChangeRequest : email_changes
    Company "1" --> "0..*" EmailAlertSetting : email_alert_settings
    Company "1" --> "0..*" EmailAlertDelivery : email_alert_deliveries
    Company "1" --> "0..*" Category : tenant_data
    Company "1" --> "0..*" Product : tenant_data
    Company "1" --> "0..*" StockMovement : tenant_data
    Company "1" --> "0..*" AuditLog : audit
    Company "1" --> "0..*" CashRegister : tenant_data
    Company "1" --> "0..*" Sale : tenant_data
    Company "1" --> "0..*" Payable : tenant_data
    Category "1" --> "0..*" Product : products
    Product "1" --> "0..*" Product : kit_component
    Product "1" --> "0..*" StockMovement : movements
    User "1" --> "0..*" CashRegister : opens
    User "1" --> "0..*" Sale : creates
    User "1" --> "0..*" StockMovement : registers
    User "1" --> "0..*" AuditLog : performs
    CashRegister "1" --> "0..*" Sale : contains
    Sale "1" --> "1..*" SaleItem : items
    Sale "1" --> "1..*" Payment : payments
    Product "1" --> "0..*" SaleItem : sold
```

## Observações

- `Company` fica no banco central e representa uma adega.
- Os dados operacionais ficam no banco MySQL da adega selecionada.
- `ActivationKey` permite gerar keys avulsas ou vinculadas a uma empresa.
- `Product` possui relacionamento autorreferente para suportar kits.
- `Payable` alimenta alertas de contas vencidas e próximas do vencimento.
- Permissões são controladas no modelo `User` e aplicadas nas rotas.

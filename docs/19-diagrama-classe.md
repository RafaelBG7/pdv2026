# 19 - Diagrama de Classe

## Diagrama Mermaid

```mermaid
classDiagram
    class User {
        +Integer id
        +String username
        +String first_name
        +String last_name
        +String email
        +String phone
        +String password_hash
        +String role
        +Boolean is_active
        +DateTime created_at
        +set_password(password)
        +check_password(password)
        +full_name
        +masked_email
        +password_fingerprint
    }

    class Category {
        +Integer id
        +String name
        +DateTime created_at
        +products
    }

    class Product {
        +Integer id
        +String name
        +String barcode
        +Integer category_id
        +Float cost_price
        +Float sale_price
        +Integer stock_quantity
        +Boolean active
        +Boolean is_kit
        +Integer kit_component_product_id
        +Integer kit_component_quantity
        +DateTime created_at
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
        +sales
    }

    class Sale {
        +Integer id
        +DateTime created_at
        +Float total_amount
        +Float discount_amount
        +Float final_amount
        +String payment_status
        +Integer user_id
        +Integer cash_register_id
        +items
        +payments
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

    Category "1" --> "0..*" Product : products
    Product "1" --> "0..*" Product : kit_component
    User "1" --> "0..*" CashRegister : opens
    User "1" --> "0..*" Sale : creates
    CashRegister "1" --> "0..*" Sale : contains
    Sale "1" --> "1..*" SaleItem : items
    Sale "1" --> "1..*" Payment : payments
    Product "1" --> "0..*" SaleItem : sold
```

## Observações

- `Product` possui relacionamento autorreferente para suportar kits.
- `Sale` remove itens e pagamentos em cascata quando excluída pelo ORM.
- Não há relacionamento explícito `User.sales` no model, embora a FK exista.
- `CashRegister.sales` usa `backref`.

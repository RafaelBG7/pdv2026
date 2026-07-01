# 03 - Arquitetura

## Visão Arquitetural

O projeto usa arquitetura monolítica web server-side:

- Flask recebe requisições HTTP.
- Blueprints organizam rotas por domínio.
- Templates Jinja2 renderizam HTML no servidor.
- JavaScript adiciona interações no cliente.
- SQLAlchemy acessa o SQLite local.
- Flask-Login gerencia sessão autenticada.

```mermaid
graph TD
    Browser["Navegador"] --> Flask["Flask App"]
    Flask --> Blueprints["Blueprints: auth, catalog, main"]
    Blueprints --> Models["Modelos SQLAlchemy"]
    Models --> SQLite["SQLite database/adega_jf.db"]
    Flask --> Templates["Templates Jinja2"]
    Templates --> Static["CSS e JavaScript"]
```

## Camadas

### Frontend

Implementado em:

- `app/templates/`
- `app/static/css/style.css`
- `app/static/js/main.js`

Características:

- Renderização server-side.
- Bootstrap 5 via CDN.
- Tema light/dark salvo em `localStorage`.
- Menu lateral recolhível salvo em `localStorage`.
- Autocomplete de produtos e categorias.
- Cálculo visual de totais, desconto, pagamento, falta e troco.
- Atalhos `F2` para pagamento e `F3` para desconto.

### Backend

Implementado em:

- `app/__init__.py`
- `app/routes/auth.py`
- `app/routes/catalog.py`
- `app/routes/main.py`
- `app/models/`
- `app/extensions.py`

Responsabilidades:

- Criar aplicação.
- Registrar blueprints.
- Inicializar banco.
- Garantir colunas adicionadas manualmente.
- Autenticar usuários.
- Executar regras de venda, estoque, caixa e relatórios.

### Banco de Dados

SQLite local:

```text
database/adega_jf.db
```

Tabelas:

- `users`
- `categories`
- `products`
- `cash_registers`
- `sales`
- `sale_items`
- `payments`

## Fluxo de Requisição

```mermaid
sequenceDiagram
    participant U as Usuario
    participant B as Navegador
    participant F as Flask
    participant R as Rota
    participant DB as SQLite
    U->>B: Acao na tela
    B->>F: GET/POST HTTP
    F->>R: Resolve blueprint/rota
    R->>DB: Consulta ou grava via SQLAlchemy
    DB-->>R: Dados
    R-->>F: Template + contexto ou redirect
    F-->>B: HTML
    B-->>U: Tela atualizada
```

## Fluxo de Autenticação

```mermaid
flowchart TD
    A["GET /login"] --> B["Exibe formulário"]
    B --> C["POST /login"]
    C --> D{"form_type=register?"}
    D -- "Sim" --> E["Valida usuario, senha e confirmacao"]
    E --> F["Cria usuario admin e autentica"]
    D -- "Nao" --> G["Busca User por username"]
    G --> H{"Senha confere?"}
    H -- "Sim" --> I["login_user"]
    H -- "Nao" --> J["Flash erro"]
    F --> K["Redirect /dashboard"]
    I --> K
```

## Fluxo de Persistência

- Modelos são declarados com Flask-SQLAlchemy.
- `db.create_all()` cria tabelas ausentes.
- Funções `ensure_*_columns()` adicionam colunas ausentes com `ALTER TABLE`.
- Operações usam `db.session.add()`, `db.session.flush()`, `db.session.commit()` e `db.session.rollback()` quando há erro de integridade.

## Blueprints

| Blueprint | Prefixo | Arquivo | Responsabilidade |
|---|---|---|---|
| `auth` | sem prefixo | `app/routes/auth.py` | Login, logout, configurações |
| `catalog` | `/catalogo` | `app/routes/catalog.py` | Produtos e categorias |
| `main` | sem prefixo | `app/routes/main.py` | Dashboard, vendas, caixa, relatórios |

## Ponto de Entrada

Fábrica real:

```python
from app import create_app
```

Problema atual:

```python
from app import create_apppy
```

em `app.py`. Deve ser corrigido para:

```python
from app import create_app
```

## Decisões Técnicas Atuais

- Monólito simples para reduzir complexidade.
- SQLite para operação local.
- Templates server-side para acelerar entrega.
- Sem camada Service/Repository dedicada; regras ficam nas rotas e funções auxiliares.
- Migrações manuais provisórias.

## Pontos de Evolução Arquitetural

- Criar camada de serviços para venda, caixa e estoque.
- Adotar Alembic/Flask-Migrate.
- Separar validações de formulário.
- Criar API JSON versionada.
- Adicionar paginação e índices adicionais.
- Centralizar logs e tratamento de exceções.

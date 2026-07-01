# 08 - Back-end

## Visão Geral

O backend é uma aplicação Flask organizada por fábrica de aplicação, extensões, modelos e blueprints.

```text
app/
├── __init__.py
├── extensions.py
├── models/
└── routes/
```

## Fábrica da Aplicação

Arquivo: `app/__init__.py`.

Responsabilidades:

- Criar instância Flask.
- Carregar `Config`.
- Inicializar `db` e `login_manager`.
- Registrar blueprints.
- Criar tabelas.
- Executar migrações manuais.
- Criar usuário `admin` se não existir.
- Configurar `user_loader`.
- Configurar página 404.
- Injetar usuário e alertas de estoque no contexto dos templates.

## Extensões

Arquivo: `app/extensions.py`.

Extensões:

- `db = SQLAlchemy()`.
- `login_manager = LoginManager()`.

Configuração de login:

- `login_view = 'auth.login'`.
- Mensagem: `Faça login para acessar esta página.`.
- Categoria: `warning`.

## Configuração

Arquivo: `config.py`.

Classe: `Config`.

- Cria diretório `database/`.
- Usa `SECRET_KEY` do ambiente ou padrão.
- Define URI SQLite.
- Desativa tracking de modificações SQLAlchemy.
- Mantém `DEBUG=True`.

## Models

Modelos:

- `User`.
- `Category`.
- `Product`.
- `CashRegister`.
- `Sale`.
- `SaleItem`.
- `Payment`.

Não há camada Repository. As rotas acessam os modelos diretamente.

## Rotas de Autenticação

Arquivo: `app/routes/auth.py`.

Funções:

- `login()`: login e cadastro.
- `logout()`: encerra sessão.
- `settings()`: atualiza perfil, email e senha.

Validações:

- Login valida senha.
- Cadastro valida usuário, senha mínima, confirmação e duplicidade.
- Alteração de senha valida senha atual, tamanho e confirmação.

## Rotas de Catálogo

Arquivo: `app/routes/catalog.py`.

Funções auxiliares:

- `parse_money()`.
- `parse_optional_money()`.
- `parse_int()`.
- `populate_product()`.

Rotas:

- Produtos.
- Novo produto.
- Editar produto.
- Atualização rápida.
- Alternar status.
- Excluir produto.
- Categorias.
- Atualizar categoria.
- Excluir categoria.

Tratamento de erros:

- `IntegrityError` para código de barras duplicado e categoria duplicada.

## Rotas Principais

Arquivo: `app/routes/main.py`.

Constantes:

- `PAYMENT_METHODS`.

Funções auxiliares:

- Parsing e formatação: `parse_money`, `format_brl`, `parse_quantity`, `parse_date`.
- Venda: `sale_form_state`, `stock_source_for_product`, `sale_item_profit`, `sale_profit`.
- Caixa: `open_cash_register`, `cash_register_profit`, `cash_register_total_sold`, `cash_register_expected_amount`.
- Relatórios: `report_period_range`, `build_sales_report`, `build_sales_chart`.

Rotas:

- `dashboard()`.
- `sales()`.
- `reports()`.
- `new_sale()`.
- `sale_detail()`.
- `cash_register()`.
- `open_cash_register_route()`.
- `close_cash_register_route()`.

## Validações Importantes no Servidor

- Caixa aberto antes de vender.
- Produto ativo antes de vender.
- Kit configurado antes de vender.
- Estoque suficiente antes de gravar venda.
- Venda com ao menos um item.
- Pagamento total suficiente.
- Nome obrigatório de produto.
- Produto kit com base e quantidade.
- Categoria não vazia.
- Categoria sem produtos para exclusão.
- Valor de fechamento do caixa exatamente igual ao esperado.

## Tratamento de Erros

Implementado:

- Flash messages para erro de validação.
- `IntegrityError` em cadastro/edição de produto e categoria.
- Página 404 customizada.

Não implementado:

- Handler global para 500.
- Logs estruturados.
- Retorno JSON de erro.
- Captura centralizada de exceções.

## Logs

Não há logging customizado. O sistema depende do log padrão do Flask/servidor.

## Serviços e Repositórios

Diretório `app/services/` existe, mas está vazio além de `__init__.py`.

Status:

- Planejado para evolução.
- Regras de negócio atualmente ficam nas rotas.

## Riscos Técnicos

- Regras de venda e estoque concentradas em uma função grande (`new_sale`).
- Sem transações explícitas para concorrência.
- Sem paginação em listagens.
- Sem migrações versionadas.
- `app.py` quebrado por import incorreto.

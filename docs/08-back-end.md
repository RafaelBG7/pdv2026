# 08 - Back-end

## Visão Geral

O backend é uma aplicação Flask organizada por fábrica de aplicação, blueprints, modelos e serviços auxiliares.

```text
app/
├── __init__.py
├── backup.py
├── error_logging.py
├── extensions.py
├── permissions.py
├── services/
├── tenant.py
├── models/
├── routes/
├── static/
└── templates/
```

## Fábrica da Aplicação

Arquivo:

- `app/__init__.py`

Responsabilidades:

- Criar instância Flask.
- Carregar `Config`.
- Inicializar `db` e `login_manager`.
- Criar banco central se necessário.
- Registrar blueprints.
- Criar tabelas centrais.
- Garantir colunas de compatibilidade.
- Criar usuário master do sistema.
- Aplicar bloqueio por assinatura/key.
- Injetar notificações no template base.
- Executar backup automático quando devido.
- Registrar handlers de erro.

## Blueprints

### `auth_bp`

Arquivo:

- `app/routes/auth.py`

Cuida de:

- Login/logout/cadastro.
- Assinatura e ativação.
- Painel master.
- Logs do master.
- Configurações.
- Equipe.
- Geração de key.
- Backup.
- Download do modelo de importação.

### `catalog_bp`

Arquivo:

- `app/routes/catalog.py`

Cuida de:

- Produtos.
- Categorias.
- Kits.
- Estoque mínimo.
- Importação de planilha.
- Dispensa de notificação de estoque.

### `main_bp`

Arquivo:

- `app/routes/main.py`

Cuida de:

- Dashboard.
- Vendas.
- Caixa.
- Relatórios.
- Contas a pagar.
- Exportação CSV.
- Movimentações de estoque.
- Auditoria operacional e master.

## Serviços

### `app/services/stock_service.py`

Centraliza toda alteração de saldo de produto.

Funções principais:

- `register_stock_movement(...)`
- `increase_stock(...)`
- `decrease_stock(...)`
- `adjust_stock(...)`

Responsabilidades:

- validar quantidade;
- respeitar `Company.allow_negative_stock`;
- calcular saldo anterior e novo;
- atualizar `products.stock_quantity`;
- criar `stock_movements`;
- usar a mesma sessão/transação da operação chamadora.

Em MySQL, o produto é travado com `SELECT ... FOR UPDATE` quando aplicável para reduzir
risco de concorrência em baixa/ajuste de estoque.

### `app/services/audit_service.py`

Centraliza registros de auditoria.

Funções principais:

- `record_audit_event(...)`
- `changed_values(...)`
- `sanitize_payload(...)`

Responsabilidades:

- mascarar campos sensíveis;
- registrar usuário, IP, rota, método, user-agent e request id;
- gravar valores antigos e novos em JSON;
- funcionar dentro ou fora de uma requisição Flask.

## Tenant

Arquivo:

- `app/tenant.py`

Responsabilidades:

- Definir nome do banco da adega.
- Criar banco MySQL da adega.
- Criar engine por tenant.
- Abrir sessão da adega atual.
- Sincronizar usuário/empresa no banco operacional.
- Apagar banco ao excluir adega, quando permitido.

## Permissões

Arquivo:

- `app/permissions.py`

Uso:

```python
@permission_required('can_manage_sales')
```

O decorator bloqueia usuário sem permissão e redireciona para o dashboard com mensagem.

## Backup

Arquivo:

- `app/backup.py`

Funções principais:

- `backup_due(company)`
- `create_company_backup(company, reason='manual')`
- `build_database_dump(engine, database_name)`

O backup gera um arquivo `.sql` com estrutura e dados do banco da adega.

Em produção, `scripts/backup_mysql.sh` também gera uma cópia diária completa do MySQL por meio do serviço Docker `backup`, sem depender de requisições ao Flask.

## Estoque na venda

A empresa controla a regra por `Company.allow_negative_stock`:

- Desativado: a venda é recusada quando não há saldo suficiente.
- Ativado: a venda é concluída, o saldo pode ficar negativo e o sistema exibe aviso.

A tela de pagamento é um modal separado da composição dos itens. O backend continua responsável por validar pagamentos, gravar venda e itens, baixar estoque, criar `stock_movements`, registrar auditoria e vincular o caixa.

Se qualquer baixa falhar, a transação é revertida e não ficam venda, pagamentos ou movimentos parciais.

## Logs de Erro

Arquivo:

- `app/error_logging.py`

Registra erro com:

- Usuário.
- Método.
- Endpoint.
- Caminho.
- Formulário mascarado.
- Tempo de requisição.
- Request id.

## Configuração

Arquivo:

- `config.py`

Variáveis principais:

- `DATABASE_URL`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_DATABASE`
- `MYSQL_TENANT_DATABASE_PREFIX`
- `MYSQL_TENANT_DATABASE_URL_TEMPLATE`
- `MYSQL_SERVER_DATABASE_URL`
- `SECRET_KEY`
- `PORT`

## Rotas Críticas

| Rota | Função |
|---|---|
| `/login` | Login e cadastro. |
| `/assinatura` | Ativação por key. |
| `/master/adegas` | Gestão master. |
| `/configuracoes` | Usuário, equipe, financeiro, backup, importação, exportação e keys. |
| `/catalogo/produtos` | Produtos. |
| `/catalogo/categorias` | Categorias. |
| `/vendas/nova` | Registrar venda. |
| `/caixa` | Caixa atual e anteriores. |
| `/estoque/movimentacoes` | Histórico de estoque. |
| `/estoque/entrada` | Entrada manual de estoque. |
| `/estoque/ajuste` | Ajuste manual de estoque. |
| `/auditoria` | Auditoria da adega. |
| `/master/auditoria` | Auditoria central do master. |
| `/relatorios` | Relatórios. |
| `/contas-a-pagar` | Contas a pagar. |
| `/exportacoes/<tipo>` | Exportação CSV. |

## Padrões de Implementação

- Rotas protegidas devem usar `@login_required`.
- Rotas sensíveis também devem usar `@permission_required`.
- Dados operacionais devem usar `tenant_session()`.
- Dados globais/master devem usar `db.session`.
- Após POST bem-sucedido, usar redirect.
- Mensagens para usuário devem usar `flash()`.
- Validações importantes devem ficar no backend.

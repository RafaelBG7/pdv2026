# Girofy - PDV Web

Sistema PDV web para adegas, pequenos mercados e comércios locais. O projeto roda em Flask, usa MySQL como banco relacional, templates HTML/Jinja no frontend e já opera com base multiadega para um modelo SaaS.

## Visão Geral

O Girofy é um sistema de ponto de venda criado para organizar a operação diária de uma adega. Ele substitui controles manuais em papel ou planilhas por uma interface web acessível pelo navegador.

O sistema cobre:

- registro de vendas;
- controle de produtos;
- controle de categorias;
- controle de estoque;
- abertura e fechamento de caixa;
- relatórios por período;
- controle de usuários e permissões;
- contas a pagar;
- notificações operacionais;
- operação local em rede;
- separação de dados por adega;
- painel master para administração das adegas;
- assinatura/key de ativação por adega;
- importação e exportação de dados;
- backup por período ou manual;
- logs de erro visíveis no painel master;
- base multiadega para operação SaaS.

## Objetivo do Projeto

O projeto resolve problemas comuns de adegas e pequenos comércios:

- substituir controle manual de produtos, vendas e caixa;
- organizar estoque e estoque mínimo;
- registrar vendas com valores corretos;
- controlar dinheiro esperado no fechamento do caixa;
- calcular desconto, troco e lucro;
- acompanhar vendas por período;
- alertar sobre estoque baixo e contas próximas do vencimento;
- permitir que outro computador da mesma rede acesse o PDV pelo navegador;
- operar múltiplas adegas com bancos separados, planos, assinatura e key de ativação.

## Avaliação Atual

O sistema já está em uma fase forte para uso como PDV SaaS local/controlado. A base multiadega, o painel master, o controle por key, as permissões, os backups, os logs e a separação por banco de dados tornam o projeto bem mais completo do que um PDV simples.

Pontos mais maduros:

- operação de venda, caixa, produtos e relatórios;
- isolamento por adega com MySQL;
- painel master para suporte e administração;
- fluxo de assinatura/key inicial;
- permissões para funcionário, gerente e admin;
- importação, exportação, backup e logs;
- dashboard operacional com indicadores úteis;
- ambiente OCI Free Tier publicado em porta alta;
- deploy automatizado por GitHub Actions.

Pontos que ainda merecem prioridade antes de produção pública:

- CSRF nos formulários;
- migrações versionadas com Alembic/Flask-Migrate;
- auditoria de ações de negócio;
- restauração guiada de backup;
- cobrança real e regras concretas para Basic/Pro;
- domínio definitivo com HTTPS;
- assinatura digital dos instaladores desktop.

## Tecnologias Utilizadas

| Tecnologia | Uso no projeto |
|---|---|
| Python | Linguagem principal do backend. |
| Flask | Framework web usado para rotas, templates e servidor local. |
| Flask-Login | Login, logout, sessão de usuário e proteção de rotas. |
| Flask-SQLAlchemy | Integração do Flask com SQLAlchemy. |
| SQLAlchemy | ORM e conexão com MySQL. Também é usado em consultas parametrizadas e criação de bancos por adega. |
| PyMySQL | Driver MySQL usado na URL `mysql+pymysql://...`. |
| MySQL | Banco relacional principal. Existe um banco central e bancos separados por adega. |
| Jinja2 | Renderização de templates HTML. |
| HTML | Estrutura das telas. |
| CSS | Interface visual em `app/static/css/style.css`, com tema claro/escuro e layout responsivo. |
| JavaScript | Interações da interface em `app/static/js/main.js`, incluindo menu lateral, autocomplete, venda, desconto, atalhos e tema. |
| Bootstrap | CSS/JS carregado via CDN nos templates para base visual e componentes. |
| unittest | Testes automatizados de rotas e regras principais. |

Observação: o projeto lê automaticamente um arquivo `.env` na raiz e também aceita variáveis exportadas no terminal.

## Estrutura de Pastas

```text
pdv-adega-jf/
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── .env.example
├── app/
│   ├── __init__.py
│   ├── extensions.py
│   ├── error_logging.py
│   ├── permissions.py
│   ├── tenant.py
│   ├── models/
│   ├── routes/
│   ├── static/
│   └── templates/
├── database/
├── docs/
├── logs/
├── scripts/
└── tests/
```

### Arquivos da raiz

| Arquivo/Pasta | Função |
|---|---|
| `app.py` | Ponto de entrada da aplicação. Cria o app e roda em `0.0.0.0` na porta definida por `PORT`, com padrão `5003`. |
| `config.py` | Configuração principal. Monta URLs MySQL, `SECRET_KEY`, banco central, prefixo de bancos das adegas e pasta de logs. |
| `requirements.txt` | Dependências Python necessárias para rodar o projeto. |
| `README.md` | Documentação principal do projeto. |
| `.env.example` | Modelo de variáveis de ambiente recomendado para configurar o projeto. |
| `database/` | Arquivos SQLite antigos preservados da fase anterior do projeto. O sistema atual usa MySQL. |
| `docs/` | Documentação complementar já existente, separada por temas como arquitetura, segurança, testes e roadmap. |
| `logs/` | Armazena `errors.log`, usado pelo sistema de logs de erro. |
| `scripts/migrate_sqlite_to_mysql.py` | Script auxiliar para migração dos dados SQLite antigos para MySQL. |
| `tests/test_routes.py` | Testes automatizados das rotas, permissões, vendas, caixa, relatórios e isolamento por adega. |

### Pasta `app/`

| Arquivo/Pasta | Função |
|---|---|
| `app/__init__.py` | Factory `create_app`, registro de blueprints, criação de tabelas, ajustes manuais de colunas, login manager, bloqueio por assinatura, notificações e handlers de erro. |
| `app/extensions.py` | Instâncias globais de `SQLAlchemy` e `LoginManager`. |
| `app/error_logging.py` | Logs detalhados de erro com `request_id`, usuário, endpoint, método, formulário protegido e rotação de arquivo. |
| `app/permissions.py` | Decorator `permission_required` e nomes das permissões do sistema. |
| `app/tenant.py` | Gerencia banco separado por adega, criação automática de databases MySQL, sessão por tenant e sincronização de empresa/usuários no banco da adega. |
| `app/models/` | Modelos SQLAlchemy: empresas, usuários, produtos, categorias, caixa, vendas, itens, pagamentos e contas a pagar. |
| `app/routes/` | Rotas Flask separadas por domínio: autenticação/configurações, catálogo e operação principal. |
| `app/templates/` | Templates HTML/Jinja das telas. |
| `app/static/css/style.css` | Estilos da interface, tema claro/escuro, layout, tabelas, cards, vendas, caixa e responsividade. |
| `app/static/js/main.js` | Comportamentos de frontend: navbar colapsável, tema, filtros, autocomplete, venda, pagamento, desconto e atalhos. |

## Funcionalidades Implementadas

### Login, logout e cadastro inicial

Onde fica:

- Tela: `/login`
- Código: `app/routes/auth.py`
- Template: `app/templates/login.html`
- Tabelas: `users`, `companies`

O sistema permite:

- login com usuário e senha;
- logout;
- cadastro de uma nova adega pela tela de login;
- criação automática de uma empresa/adega;
- confirmação de e-mail por código antes do primeiro acesso;
- recuperação de senha por link enviado por e-mail;
- uso de key de ativação quando informada no cadastro;
- opção "Não tenho key", criando a adega bloqueada até ativação;
- criação do primeiro usuário como `admin`, chamado de master da adega.

Regras importantes:

- usuário não pode ser vazio;
- senha de cadastro precisa ter pelo menos 3 caracteres;
- confirmação de senha precisa bater;
- username deve ser único;
- e-mail é obrigatório no cadastro inicial para receber o código de confirmação;
- usuário sem e-mail confirmado não consegue entrar;
- usuário inativo não consegue entrar;
- adega inativa não permite login de usuários comuns;
- usuário `master` do sistema é redirecionado ao painel master.

### Usuário master inicial

Na primeira inicialização, caso não exista um usuário `master`, o sistema cria:

```text
Usuário: master
Senha: master123
```

Esse usuário é o master do sistema inteiro, não apenas de uma adega.

### Painel master de adegas

Onde fica:

- Rota: `/master/adegas`
- Código: `app/routes/auth.py`
- Template: `app/templates/master/companies.html`
- Tabelas centrais: `companies`, `users`
- Tabelas operacionais consultadas: `products`, `sales`, `cash_registers`

O master do sistema pode:

- listar todas as adegas;
- alternar visualização em tabela ou blocos;
- editar nome, status, plano, ciclo de cobrança, datas e key;
- inativar adegas;
- excluir adegas;
- acessar a adega como master;
- sair do acesso de uma adega;
- consultar quantidade de usuários, produtos, vendas e caixas;
- ver logs de erro recentes;
- limpar logs;
- acompanhar plano, renovação e dias restantes.

Regras importantes:

- apenas usuário com `role = master` acessa esse painel;
- o master não pode inativar ou excluir a própria adega do master;
- ao excluir uma adega, o sistema remove os usuários da empresa e apaga o banco MySQL da adega.

### Assinatura e key de ativação

Onde fica:

- Ativação: `/assinatura`
- Planos: `/assinaturas`
- Código: `app/routes/auth.py`
- Templates: `app/templates/subscription/activation.html` e `app/templates/subscription/plans.html`
- Tabelas: `companies`, `activation_keys`

O sistema possui controle de assinatura por adega:

- plano atual;
- ciclo mensal/anual;
- data de início;
- data de renovação;
- key de ativação;
- bloqueio quando assinatura vence ou empresa está inativa.

Os planos Basic e Pro existem como tela estética/comercial, sem cobrança real integrada.

Regras importantes:

- usuário comum/admin de adega vencida é redirecionado para `/assinatura`;
- key pode ser gerada pelo master como avulsa ou vinculada a uma adega;
- key válida aplica plano e nova data de renovação;
- cadastro sem key cria a adega, mas bloqueia ações até ativação;
- usuário `master` do sistema não é bloqueado por assinatura.

### Configurações, usuário, aparência, equipe e financeiro

Onde fica:

- Rota: `/configuracoes`
- Código: `app/routes/auth.py`
- Template: `app/templates/settings/index.html`
- Tabelas: `users`, `companies`

O sistema permite:

- editar nome, sobrenome e telefone do usuário;
- alterar email;
- alterar email com confirmação pelo e-mail antigo quando já existe e-mail confirmado;
- alterar senha;
- configurar alertas críticos por e-mail por tipo de evento;
- alternar tema light/dark pela aba Aparência;
- gerenciar equipe da adega;
- contratar usuário;
- alterar permissões de funcionário;
- ativar/inativar funcionário;
- configurar taxas de Pix, débito e crédito para desconto no lucro.

Regras importantes:

- senha atual precisa ser informada para trocar senha;
- troca de e-mail confirmada envia link para o e-mail antigo;
- alertas críticos podem ser direcionados para emails específicos por adega;
- nova senha precisa ter pelo menos 3 caracteres;
- funcionário comum não vê abas sensíveis como equipe, financeiro e plano;
- cada adega pode ter usuário administrador próprio;
- não é permitido criar outro usuário com username já existente;
- se um funcionário tem permissão de gerenciar produtos, também passa a poder ver produtos.

### Produtos

Onde fica:

- Lista: `/catalogo/produtos`
- Novo: `/catalogo/produtos/novo`
- Editar: `/catalogo/produtos/<id>/editar`
- Atualização rápida: `/catalogo/produtos/<id>/atualizar`
- Código: `app/routes/catalog.py`
- Templates: `app/templates/catalog/products.html` e `app/templates/catalog/product_form.html`
- Tabelas: `products`, `categories`

O sistema permite:

- cadastrar produto;
- listar produto;
- filtrar por nome/código, status, categoria, estoque, preço mínimo/máximo e ordenação;
- editar produto;
- atualizar produto na linha expandida;
- ativar/inativar produto;
- excluir produto;
- configurar custo, venda, estoque e estoque mínimo;
- associar categoria;
- configurar produto como kit;
- importar produtos por CSV ou XLSX.

Campos principais usados:

- nome;
- código de barras;
- categoria;
- valor de custo;
- valor de venda;
- estoque;
- estoque mínimo;
- status ativo/inativo;
- kit;
- produto base do kit;
- quantidade do produto base consumida pelo kit.

Regras importantes:

- produto precisa ter nome;
- código de barras não pode duplicar dentro da mesma adega;
- produto pertence à adega atual;
- funcionário comum pode ver produtos se tiver permissão, mas não necessariamente editar;
- kit precisa ter produto base e quantidade maior que zero;
- produto base do kit não pode ser o próprio kit;
- lucro exibido considera venda menos custo;
- alerta de estoque baixo depende de estoque mínimo configurado.

### Importação de produtos por planilha

Onde fica:

- Tela: `Configurações > Importação`
- Envio: `POST /catalogo/produtos/importar`
- Modelo: download pela aba de importação
- Código: `app/routes/catalog.py`
- Tabela: `products`, `categories`

Formatos aceitos:

- `.csv`
- `.xlsx`

Colunas reconhecidas:

- categoria;
- produto, nome, nome_produto, product, name;
- valor de custo, custo, preço de custo, cost_price, cost;
- valor de venda, venda, preço de venda, sale_price, price.
- estoque atual, estoque_atual, estoque, stock_quantity, stock;
- estoque mínimo, estoque_minimo, min_stock_quantity, min_stock.

Regras importantes:

- apenas dono/admin autorizado da adega pode importar;
- a importação é feita dentro da adega atual;
- categoria é criada se não existir na adega;
- produto existente com mesmo nome é atualizado;
- produto novo é criado ativo;
- linhas sem nome de produto são ignoradas.

### Categorias

Onde fica:

- Rota: `/catalogo/categorias`
- Atualizar: `/catalogo/categorias/<id>/atualizar`
- Excluir: `/catalogo/categorias/<id>/excluir`
- Código: `app/routes/catalog.py`
- Template: `app/templates/catalog/categories.html`
- Tabelas: `categories`, `products`

O sistema permite:

- cadastrar categoria;
- listar categorias;
- buscar por nome;
- filtrar por categorias com produtos ou vazias;
- ordenar por nome, quantidade de produtos ou data;
- editar nome pela linha expandida;
- excluir categoria.

Regras importantes:

- categoria precisa ter nome;
- categoria é única apenas dentro da adega atual;
- adegas diferentes podem ter categoria com o mesmo nome;
- não é possível excluir categoria com produtos vinculados;
- categoria pertence à adega atual.

### Caixa

Onde fica:

- Caixa: `/caixa`
- Abrir: `/caixa/abrir`
- Fechar: `/caixa/fechar`
- Detalhes: `/caixa/<id>`
- Código: `app/routes/main.py`
- Templates: `app/templates/cash_register.html` e `app/templates/cash_register_detail.html`
- Tabela: `cash_registers`

O sistema permite:

- abrir caixa com valor inicial;
- bloquear abertura de segundo caixa se já existe caixa aberto;
- exibir caixa atual;
- consultar caixas anteriores;
- fechar caixa;
- validar valor de fechamento;
- ver detalhes de caixa fechado;
- consultar formas vendidas, horário de pico e produtos mais vendidos.

Regras importantes:

- venda exige caixa aberto;
- fechamento precisa bater exatamente com valor inicial + total vendido;
- se faltar dinheiro, mostra valor faltante;
- se exceder, mostra valor excedido;
- lucro do caixa soma lucro das vendas do caixa.

### Vendas

Onde fica:

- Lista: `/vendas`
- Nova venda: `/vendas/nova`
- Detalhe: `/vendas/<id>`
- Código: `app/routes/main.py`
- Templates: `app/templates/sales/index.html`, `app/templates/sales/form.html`, `app/templates/sales/detail.html`
- Tabelas: `sales`, `sale_items`, `payments`, `products`, `cash_registers`

O sistema permite:

- listar vendas;
- abrir tela de nova venda;
- buscar produto por autocomplete;
- adicionar múltiplos produtos;
- usar qualquer quantidade de itens;
- aplicar desconto em reais;
- pagar com dinheiro, Pix, débito e crédito;
- usar múltiplas formas de pagamento na mesma venda;
- calcular total, pago, faltante e troco;
- finalizar venda;
- ver detalhe da venda.

Regras importantes:

- caixa precisa estar aberto;
- venda precisa ter pelo menos um item;
- produto precisa existir, estar ativo e pertencer à adega;
- estoque precisa ser suficiente;
- kit desconta estoque do produto base;
- pagamento não pode ser menor que o total final;
- desconto não passa do total;
- venda reduz estoque;
- lucro por item considera custo, desconto do produto e taxas configuradas de Pix/débito/crédito;
- erro de pagamento ou estoque não reseta o pedido;
- atalho F2 abre/conclui a etapa de finalização;
- atalho F3 abre desconto.

### Relatórios

Onde fica:

- Rota: `/relatorios`
- Código: `app/routes/main.py`
- Template: `app/templates/reports/index.html`
- Tabelas: `sales`, `sale_items`, `payments`, `products`

O sistema permite:

- consultar vendas por período diário, semanal, mensal, anual ou personalizado;
- preencher automaticamente períodos padrão;
- ver total vendido;
- ver descontos;
- ver lucro;
- ver ticket médio;
- ver formas de pagamento;
- ver produtos mais vendidos;
- ver gráfico de colunas por período.

Períodos automáticos:

- diário: data atual;
- semanal: últimos 7 dias;
- mensal: últimos 30 dias;
- anual: últimos 365 dias;
- personalizado: datas escolhidas pelo usuário.

### Contas a pagar

Onde fica:

- Lista/cadastro: `/contas-a-pagar`
- Marcar como paga: `/contas-a-pagar/<id>/pagar`
- Reabrir: `/contas-a-pagar/<id>/reabrir`
- Código: `app/routes/main.py`
- Template: `app/templates/payables/index.html`
- Tabela: `payables`

O sistema permite:

- cadastrar conta a pagar;
- categorizar conta como aluguel, luz, água, internet, fornecedor, impostos ou outros;
- informar valor, vencimento e observações;
- filtrar abertas, pagas e todas;
- marcar como paga;
- reabrir conta;
- gerar alerta quando está próxima do vencimento.

Regras importantes:

- descrição é obrigatória;
- data de vencimento precisa ser válida;
- alertas aparecem quando vencida, vence hoje ou vence em até 3 dias;
- dados pertencem à adega atual.

### Notificações

Onde fica:

- Código: `app/__init__.py`
- Template base: `app/templates/base.html`

O sistema mostra notificações no topo:

- estoque baixo;
- produto sem estoque;
- conta vencida;
- conta vencendo hoje;
- conta vencendo em até 3 dias.

Regras importantes:

- alertas são filtrados pela adega atual;
- alerta de estoque pode ser dispensado;
- alertas usam estoque mínimo configurado no produto.

### Logs de erro

Onde fica:

- Código: `app/error_logging.py`
- Arquivo: `logs/errors.log`

O sistema registra:

- erros HTTP 404 e 500;
- exceções não tratadas;
- endpoint;
- método;
- caminho;
- query string;
- formulário com campos sensíveis protegidos;
- usuário autenticado;
- tempo da requisição;
- `X-Request-ID`.

## Banco de Dados MySQL

O projeto usa MySQL em dois níveis:

1. Banco central: guarda empresas, usuários, assinatura, planos e dados administrativos.
2. Banco por adega: guarda dados operacionais daquela adega.

Por padrão:

```text
Banco central: adega_central
Prefixo dos bancos das adegas: adega
Exemplo de banco de adega: adega_4_adegajf
```

### Configuração da conexão

As configurações reais lidas por `config.py` são:

| Variável | Padrão | Função |
|---|---|---|
| `SECRET_KEY` | `adega-jf-secret-key` | Chave de sessão do Flask. Deve ser alterada fora do desenvolvimento. |
| `DATABASE_URL` | Gerada automaticamente | URL completa do banco central. Se definida, sobrescreve `MYSQL_*`. |
| `MYSQL_USER` | `root` | Usuário do MySQL. |
| `MYSQL_PASSWORD` | vazio | Senha do MySQL. |
| `MYSQL_HOST` | `127.0.0.1` | Host do MySQL. |
| `MYSQL_PORT` | `3306` | Porta do MySQL. |
| `MYSQL_DATABASE` | `adega_central` | Nome do banco central. |
| `MYSQL_TENANT_DATABASE_PREFIX` | `adega` | Prefixo dos bancos de cada adega. |
| `MYSQL_TENANT_DATABASE_URL_TEMPLATE` | vazio | Template opcional para URL dos bancos das adegas. Usa `{database}`. |
| `MYSQL_SERVER_DATABASE_URL` | MySQL no banco `mysql` | URL administrativa usada para criar/dropar databases. |
| `PORT` | `5003` | Porta do servidor Flask local. |

Exemplo de URL:

```text
mysql+pymysql://root@127.0.0.1:3306/adega_central?charset=utf8mb4
```

### Criação do banco central

O app tenta criar automaticamente o banco central se ele não existir. Também é possível criar manualmente:

```sql
CREATE DATABASE adega_central CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Criar usuário MySQL dedicado

Exemplo opcional:

```sql
CREATE USER 'adega_user'@'localhost' IDENTIFIED BY 'sua_senha_forte';
GRANT ALL PRIVILEGES ON adega_central.* TO 'adega_user'@'localhost';
GRANT ALL PRIVILEGES ON `adega\_%`.* TO 'adega_user'@'localhost';
FLUSH PRIVILEGES;
```

Para criação automática de bancos das adegas, o usuário precisa ter permissão de `CREATE DATABASE` e `DROP DATABASE`, ou a variável `MYSQL_SERVER_DATABASE_URL` deve apontar para um usuário administrativo.

### Tabelas e campos principais

#### `companies`

Representa uma adega/empresa.

| Campo | Função |
|---|---|
| `id` | Chave primária. |
| `name` | Nome da adega. |
| `database_path` | Nome do banco MySQL da adega. |
| `active` | Indica se a adega está ativa. |
| `subscription_plan` | Plano atual: Essencial, Profissional, Premium, Basic/Pro na tela comercial. |
| `billing_cycle` | Ciclo mensal/anual. |
| `subscription_started_at` | Data de início da assinatura. |
| `subscription_renews_at` | Data de renovação. |
| `activation_key` | Key de ativação da adega. |
| `activation_key_updated_at` | Data/hora da última alteração da key. |
| `pix_fee_enabled`, `debit_fee_enabled`, `credit_fee_enabled` | Ativação das taxas por forma de pagamento. |
| `pix_fee_percent`, `debit_fee_percent`, `credit_fee_percent` | Percentuais de taxa. |
| `created_at` | Data de criação. |

#### `users`

Representa usuários do sistema.

| Campo | Função |
|---|---|
| `id` | Chave primária. |
| `username` | Login único. |
| `first_name`, `last_name` | Nome e sobrenome. |
| `email` | Email. |
| `phone` | Telefone. |
| `password_hash` | Senha com hash. |
| `role` | `master`, `admin` ou `operator`. |
| `company_id` | FK para `companies.id`. |
| `is_active` | Usuário ativo/inativo. |
| `can_view_products` | Permissão para ver produtos. |
| `can_manage_products` | Permissão para gerenciar produtos. |
| `can_manage_categories` | Permissão para categorias. |
| `can_manage_sales` | Permissão para vendas. |
| `can_manage_cash_register` | Permissão para caixa. |
| `can_view_reports` | Permissão para relatórios. |
| `can_manage_payables` | Permissão para contas a pagar. |
| `can_manage_settings` | Permissão para configurações. |
| `created_at` | Data de criação. |

#### `categories`

Categorias de produtos.

| Campo | Função |
|---|---|
| `id` | Chave primária. |
| `name` | Nome da categoria. |
| `company_id` | FK para `companies.id`. |
| `created_at` | Data de criação. |

#### `products`

Produtos vendidos.

| Campo | Função |
|---|---|
| `id` | Chave primária. |
| `name` | Nome do produto. |
| `barcode` | Código de barras opcional. |
| `category_id` | FK para `categories.id`. |
| `company_id` | FK para `companies.id`. |
| `cost_price` | Preço de custo. |
| `sale_price` | Preço de venda. |
| `stock_quantity` | Estoque atual. |
| `min_stock_quantity` | Estoque mínimo para alerta. |
| `active` | Produto ativo/inativo. |
| `is_kit` | Indica se é kit. |
| `kit_component_product_id` | Produto base descontado quando o kit é vendido. |
| `kit_component_quantity` | Quantidade do produto base consumida pelo kit. |
| `created_at` | Data de criação. |

#### `cash_registers`

Caixas abertos/fechados.

| Campo | Função |
|---|---|
| `id` | Chave primária. |
| `opened_at` | Data/hora de abertura. |
| `closed_at` | Data/hora de fechamento. |
| `opening_amount` | Valor inicial. |
| `closing_amount` | Valor final informado. |
| `status` | `open` ou `closed`. |
| `user_id` | Usuário que abriu. |
| `company_id` | FK para `companies.id`. |

#### `sales`

Venda finalizada.

| Campo | Função |
|---|---|
| `id` | Chave primária. |
| `created_at` | Data/hora da venda. |
| `total_amount` | Total bruto. |
| `discount_amount` | Desconto em reais. |
| `final_amount` | Total final. |
| `payment_status` | Status do pagamento. |
| `user_id` | Usuário que registrou. |
| `company_id` | FK para `companies.id`. |
| `cash_register_id` | FK para `cash_registers.id`. |

#### `sale_items`

Itens da venda.

| Campo | Função |
|---|---|
| `id` | Chave primária. |
| `sale_id` | FK para `sales.id`. |
| `product_id` | FK para `products.id`. |
| `quantity` | Quantidade vendida. |
| `unit_price` | Preço unitário na venda. |
| `unit_cost_price` | Custo unitário na venda. |
| `total_price` | Total do item. |
| `profit_amount` | Lucro calculado do item. |

#### `payments`

Pagamentos da venda. No pedido original foi citado `sale_payments`; no código real a tabela se chama `payments`.

| Campo | Função |
|---|---|
| `id` | Chave primária. |
| `sale_id` | FK para `sales.id`. |
| `method` | `money`, `pix`, `debit` ou `credit`. |
| `amount` | Valor pago nessa forma. |

#### `payables`

Contas a pagar.

| Campo | Função |
|---|---|
| `id` | Chave primária. |
| `company_id` | FK para `companies.id`. |
| `description` | Descrição da conta. |
| `category` | Categoria da conta. |
| `amount` | Valor. |
| `due_date` | Vencimento. |
| `paid` | Paga/não paga. |
| `paid_at` | Data/hora do pagamento. |
| `notes` | Observações. |
| `created_at` | Data de criação. |

### Tabelas citadas mas não existentes no código atual

| Nome | Status |
|---|---|
| `stock_movements` | Não existe no código atual. A baixa de estoque é feita diretamente em `products.stock_quantity`. |
| `clientes` | Não existe no código atual. O sistema ainda não possui cadastro de clientes. |
| `sale_payments` | Não existe com esse nome. A tabela real é `payments`. |

### Relacionamentos principais

- `Company` possui vários `User`.
- `Category` possui vários `Product`.
- `Product` pode pertencer a uma `Category`.
- `Product` pode apontar para outro `Product` como componente de kit.
- `CashRegister` possui várias `Sale`.
- `Sale` possui vários `SaleItem`.
- `Sale` possui vários `Payment`.
- `SaleItem` aponta para `Product`.
- `Payable` pertence a uma `Company`.

## Configuração do Ambiente

### 1. Instalar Python

Recomendado: Python 3.10 ou superior. O ambiente local atual usa Python 3.13.

Verifique:

```bash
python3 --version
```

### 2. Criar ambiente virtual

Na pasta do projeto:

```bash
cd /Users/rafaelborges/pdv-adega-jf
python3 -m venv .venv
```

### 3. Ativar ambiente virtual

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows CMD:

```bat
.venv\Scripts\activate.bat
```

### 4. Instalar dependências

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5. Configurar MySQL

Com MySQL instalado e rodando, crie o banco central se desejar fazer manualmente:

```sql
CREATE DATABASE adega_central CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

O sistema também tenta criar esse banco automaticamente ao iniciar, desde que o usuário MySQL tenha permissão.

### 6. Configurar variáveis de ambiente

Copie o modelo:

```bash
cp .env.example .env
```

O projeto carrega `.env` automaticamente ao iniciar. Você também pode exportar as variáveis no terminal ou rodar informando antes do comando.

Exemplo macOS/Linux:

```bash
export MYSQL_USER=root
export MYSQL_PASSWORD=sua_senha
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_DATABASE=adega_central
export SECRET_KEY=troque-esta-chave
```

Ou em uma única linha:

```bash
MYSQL_PASSWORD=sua_senha SECRET_KEY=troque-esta-chave python app.py
```

### 7. Rodar o projeto

```bash
python app.py
```

Acesse:

```text
http://127.0.0.1:5003
```

A porta padrão é `5003` porque no macOS a porta `5000` pode estar ocupada pelo AirPlay e a `5001` costuma ficar presa em testes locais.

Para trocar a porta:

```bash
PORT=5002 python app.py
```

### 8. Compilar como aplicativo local no macOS

O projeto pode ser empacotado como um aplicativo `.app` com janela própria via WebView nativa do macOS. Ele continua usando MySQL local e lê as configurações pelo arquivo `.env`, sem embutir senhas no executável.

Compile com:

```bash
bash scripts/build_macos_app.sh
```

O aplicativo será gerado em:

```text
dist/Girofy.app
```

Para abrir pelo terminal:

```bash
open dist/Girofy.app
```

Ao abrir, o launcher sobe o servidor local em uma porta livre e mostra o sistema dentro de uma janela de aplicativo. Ele usa `dist/.env` como configuração local. Se o MySQL não estiver rodando ou alguma configuração falhar, o arquivo `dist/launcher-error.log` será criado com o erro detalhado.

### 9. Builds automáticos no GitHub

O repositório possui o workflow `.github/workflows/build-desktop.yml` para gerar automaticamente os pacotes desktop.

Ele gera:

- `Girofy-macOS.zip`, contendo `Girofy.app`;
- `Girofy-Windows.zip`, contendo `Girofy.exe`;
- `Girofy-Setup.exe`, instalador Windows com MySQL local embutido;
- um modelo `.env.example` junto do pacote quando não houver `.env`.

O workflow roda de duas formas:

```text
Actions > Build desktop apps > Run workflow
```

Ou ao publicar uma tag iniciada com `v`:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Depois da execução, os arquivos ficam em:

```text
GitHub > Actions > Build desktop apps > Artifacts
```

Quando a execução vier de uma tag `v*`, o GitHub também cria uma Release automaticamente em:

```text
GitHub > Releases
```

Essa Release recebe estes anexos:

- `Girofy-macOS.zip`;
- `Girofy-Windows.zip`.
- `Girofy-Setup.exe`.

Observação: por segurança, o GitHub não deve receber o `.env` real. Cada instalação precisa criar/copiar seu próprio `.env` ao lado do app baixado.

### 10. Instalador Windows com MySQL embutido

Para clientes Windows, o arquivo recomendado é:

```text
Girofy-Setup.exe
```

Esse instalador faz automaticamente:

- instala o aplicativo em `Arquivos de Programas\Girofy`;
- instala o MySQL Community Server local em uma pasta interna do Girofy;
- cria o serviço Windows `GirofyMySQL`;
- usa a porta local `3307`, evitando conflito com outro MySQL na porta `3306`;
- cria o banco `adega_central`;
- cria o usuário `girofy_app` com senha segura gerada automaticamente;
- gera o arquivo `.env` do aplicativo;
- cria atalhos no menu iniciar e na área de trabalho.

Os dados do banco ficam em:

```text
C:\ProgramData\Girofy\mysql-data
```

As senhas geradas ficam em:

```text
C:\ProgramData\Girofy\secrets
```

Na desinstalação, o serviço `GirofyMySQL` é removido, mas os dados em `C:\ProgramData\Girofy` são preservados para evitar perda acidental de vendas, produtos e caixas.

### 11. Assinatura digital dos instaladores

Windows Smart App Control, Microsoft Defender SmartScreen e Apple Gatekeeper podem bloquear builds sem assinatura. Isso não é resolvido por HTML, Flask ou PyInstaller; é necessário assinar os arquivos com certificados reconhecidos.

O workflow `Build desktop apps` já está preparado para assinar automaticamente quando os secrets existirem.

#### Windows

Compre/obtenha um certificado **Code Signing** para Windows, preferencialmente OV ou EV. Depois gere/exporte um arquivo `.pfx` com chave privada e cadastre estes secrets no GitHub:

```text
WINDOWS_CODESIGN_PFX_BASE64
WINDOWS_CODESIGN_PFX_PASSWORD
```

O valor `WINDOWS_CODESIGN_PFX_BASE64` deve ser o `.pfx` convertido para Base64. Também é possível configurar a variável:

```text
WINDOWS_CODESIGN_TIMESTAMP_URL
```

Se não configurar, o workflow usa:

```text
http://timestamp.digicert.com
```

Quando configurado, o workflow assina:

- `dist\Girofy\Girofy.exe`;
- `dist\installer\Girofy-Setup.exe`.

#### macOS

Para o macOS, é necessário uma conta Apple Developer e um certificado **Developer ID Application**. Cadastre estes secrets no GitHub:

```text
APPLE_DEVELOPER_ID_CERTIFICATE_BASE64
APPLE_DEVELOPER_ID_CERTIFICATE_PASSWORD
APPLE_DEVELOPER_IDENTITY
APPLE_ID
APPLE_TEAM_ID
APPLE_APP_SPECIFIC_PASSWORD
APPLE_BUILD_KEYCHAIN_PASSWORD
```

Quando configurado, o workflow:

- importa o certificado no keychain temporário do runner;
- assina `Girofy.app`;
- envia para notarização da Apple;
- aplica `stapler` no app notarizado;
- empacota o `.app` assinado em `Girofy-macOS.zip`.

Sem esses certificados, os sistemas operacionais podem continuar exibindo alertas de app não confiável.

### 12. Deploy automatizado na OCI

O repositório possui o workflow `.github/workflows/deploy-oci.yml` para publicar o Girofy na VM da Oracle Cloud. A pipeline faz:

- checkout do código;
- instalação das dependências Python;
- execução da suíte `unittest`;
- validação de sintaxe dos scripts de infraestrutura;
- sincronização do projeto para a VM com `rsync`;
- rebuild dos containers Docker;
- health check interno e público em `/login`.

Configure estes secrets no GitHub antes de rodar:

```text
OCI_DEPLOY_HOST
OCI_DEPLOY_USER
OCI_DEPLOY_PATH
OCI_SSH_PRIVATE_KEY
```

Opcionalmente configure a variável do ambiente `production`:

```text
OCI_DEPLOY_PORT=18080
```

O deploy pode ser executado manualmente em:

```text
GitHub > Actions > Deploy OCI > Run workflow
```

Também roda automaticamente em pushes para `main`, ignorando alterações somente em documentação.

O script usado pela pipeline é:

```text
scripts/deploy_oci_app.sh
```

Ele não envia `.env`, bancos, backups, logs, builds locais ou ambientes virtuais. O `.env` real fica preservado na VM.

### 13. Ambiente OCI atual

O ambiente online atual roda em uma VM Always Free compatível:

- aplicação pública em `http://IP_PUBLICO:18080`;
- Docker Compose com app Flask, MySQL e Caddy;
- MySQL sem porta pública;
- SSH restrito ao IP administrativo;
- portas 80 e 443 fechadas enquanto não houver domínio/HTTPS;
- fail2ban ativo para SSH;
- UFW com entrada pública apenas na porta alta do Girofy.

Para detalhes, veja:

```text
docs/22-oci-free-tier.md
docs/23-pipeline-deploy.md
```

## Configuração do MySQL

### Comandos básicos

Entrar sem senha:

```bash
mysql -u root
```

Entrar com senha:

```bash
mysql -u root -p
```

Ver bancos:

```sql
SHOW DATABASES;
```

Usar banco central:

```sql
USE adega_central;
```

Ver tabelas:

```sql
SHOW TABLES;
```

Ver adegas cadastradas:

```sql
SELECT id, name, database_path, active FROM companies;
```

Ver usuários:

```sql
SELECT id, username, role, company_id, is_active FROM users;
```

### Variáveis usadas pelo projeto

```env
SECRET_KEY=troque-esta-chave-em-producao
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=adega_central
MYSQL_TENANT_DATABASE_PREFIX=adega
MYSQL_TENANT_DATABASE_URL_TEMPLATE=
MYSQL_SERVER_DATABASE_URL=mysql+pymysql://root@127.0.0.1:3306/mysql?charset=utf8mb4
PUBLIC_BASE_URL=http://127.0.0.1:5003
MAIL_SMTP_SERVER=smtp.gmail.com
MAIL_SMTP_PORT=587
MAIL_SMTP_LOGIN=girofy2026@gmail.com
MAIL_SMTP_PASSWORD=sua-senha-de-app-do-gmail
MAIL_FROM_EMAIL=girofy2026@gmail.com
MAIL_FROM_NAME=Girofy
MAIL_SUPPRESS_SEND=0
PORT=5003
```

Também é possível usar:

```env
DATABASE_URL=mysql+pymysql://root:senha@127.0.0.1:3306/adega_central?charset=utf8mb4
```

Quando `DATABASE_URL` existe, ela substitui a montagem automática baseada em `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT` e `MYSQL_DATABASE`.


## Como Acessar pela Rede Local

O `app.py` já roda com:

```python
app.run(host='0.0.0.0', port=port, debug=True)
```

Isso permite acesso por outro computador da mesma rede.

No computador servidor, rode:

```bash
python app.py
```

Em outro computador da mesma rede, acesse:

```text
http://IP_DO_SERVIDOR:5003
```

### Descobrir IP no macOS

```bash
ipconfig getifaddr en0
```

Se estiver usando cabo:

```bash
ipconfig getifaddr en1
```

### Descobrir IP no Windows

```bat
ipconfig
```

Procure por `IPv4 Address`.

### Descobrir IP no Linux

```bash
hostname -I
```

ou:

```bash
ip addr
```

## Fluxo Operacional do PDV

1. O usuário acessa `/login`.
2. Faz login com usuário e senha.
3. Se for master do sistema, entra no painel de adegas.
4. Se for usuário de uma adega, entra no dashboard.
5. Cadastra categorias em `/catalogo/categorias`.
6. Cadastra produtos em `/catalogo/produtos`.
7. Configura estoque, custo, venda e estoque mínimo.
8. Abre o caixa em `/caixa`.
9. Acessa `/vendas/nova`.
10. Adiciona os produtos da venda.
11. Aplica desconto, se necessário.
12. Escolhe uma ou mais formas de pagamento.
13. Finaliza a venda.
14. O sistema baixa o estoque.
15. O sistema registra itens, pagamentos e lucro.
16. O usuário consulta vendas, caixa e relatórios.
17. No fim do turno, fecha o caixa informando o valor final.

## Regras de Negócio

- Usuário precisa estar autenticado para acessar áreas internas.
- Algumas áreas exigem permissões específicas.
- Cada adega tem seus próprios dados operacionais.
- Venda só pode ser registrada com caixa aberto.
- Não é permitido abrir dois caixas ao mesmo tempo para a mesma adega.
- Venda precisa ter pelo menos um item.
- Produto vendido precisa estar ativo.
- Produto vendido precisa pertencer à adega atual.
- Estoque precisa ser suficiente.
- Produto kit desconta estoque do produto base.
- Kit precisa ter produto base e quantidade configurados.
- Pagamento total não pode ser menor que o valor final da venda.
- O sistema calcula valor faltante quando o pagamento é insuficiente.
- O sistema calcula troco quando pagamento é maior que o total final.
- Desconto é em reais e não pode passar do total da venda.
- Venda reduz estoque imediatamente.
- Lucro considera preço de venda, custo, desconto e taxas configuradas.
- Caixa só fecha quando valor informado é igual ao valor esperado.
- Categoria com produtos vinculados não pode ser excluída.
- Categoria duplicada é validada por adega, não globalmente.
- Código de barras duplicado é validado por adega.
- Funcionário só acessa áreas permitidas.
- Assinatura vencida bloqueia usuário de adega até regularização.

## Rotas do Sistema

### Autenticação, assinatura, master e configurações

| Método | Rota | Função | Template | Login | Descrição |
|---|---|---|---|---|---|
| GET/POST | `/login` | `login` | `login.html` | Não | Exibe login, autentica usuário e cadastra nova adega. |
| GET | `/logout` | `logout` | - | Sim | Encerra sessão e redireciona para login. |
| GET/POST | `/assinatura` | `subscription_activation` | `subscription/activation.html` | Sim | Mostra status da assinatura e valida key. |
| GET | `/assinaturas` | `subscriptions` | `subscription/plans.html` | Sim | Mostra planos Basic e Pro. |
| GET | `/master/adegas` | `master_companies` | `master/companies.html` | Sim, master | Lista e gerencia adegas. |
| POST | `/master/adegas/<company_id>/editar` | `edit_company` | - | Sim, master | Edita dados, plano, renovação e key da adega. |
| GET | `/master/adegas/<company_id>/acessar` | `access_company` | - | Sim, master | Conecta o master em uma adega. |
| GET | `/master/adegas/sair-acesso` | `leave_company_access` | - | Sim, master | Sai do acesso da adega. |
| POST | `/master/adegas/<company_id>/alternar-status` | `toggle_company_status` | - | Sim, master | Ativa/inativa adega. |
| POST | `/master/adegas/<company_id>/excluir` | `delete_company` | - | Sim, master | Exclui adega, usuários e banco MySQL da adega. |
| GET/POST | `/configuracoes` | `settings` | `settings/index.html` | Sim | Perfil, email, senha, equipe, permissões, taxas e aparência. |

### Catálogo

| Método | Rota | Função | Template | Login/Permissão | Descrição |
|---|---|---|---|---|---|
| GET | `/catalogo/produtos` | `products` | `catalog/products.html` | `can_view_products` | Lista produtos com filtros e sugestões. |
| POST | `/catalogo/produtos/importar` | `import_products` | - | `can_manage_products` | Importa CSV/XLSX para a adega atual. |
| GET/POST | `/catalogo/produtos/novo` | `new_product` | `catalog/product_form.html` | `can_manage_products` | Cadastra produto. |
| GET/POST | `/catalogo/produtos/<product_id>/editar` | `edit_product` | `catalog/product_form.html` | `can_manage_products` | Edita produto. |
| POST | `/catalogo/produtos/<product_id>/atualizar` | `quick_update_product` | - | `can_manage_products` | Atualização rápida pela lista. |
| GET | `/catalogo/produtos/<product_id>/notificacao-estoque` | `dismiss_low_stock_notification` | - | `can_view_products` | Dispensa alerta de estoque baixo. |
| POST | `/catalogo/produtos/<product_id>/alternar-status` | `toggle_product` | - | `can_manage_products` | Ativa/inativa produto. |
| POST | `/catalogo/produtos/<product_id>/excluir` | `delete_product` | - | `can_manage_products` | Exclui produto. |
| GET/POST | `/catalogo/categorias` | `categories` | `catalog/categories.html` | `can_manage_categories` | Lista, filtra e cadastra categorias. |
| POST | `/catalogo/categorias/<category_id>/atualizar` | `update_category` | - | `can_manage_categories` | Atualiza categoria. |
| POST | `/catalogo/categorias/<category_id>/excluir` | `delete_category` | - | `can_manage_categories` | Exclui categoria vazia. |

### Operação

| Método | Rota | Função | Template | Login/Permissão | Descrição |
|---|---|---|---|---|---|
| GET | `/` | `dashboard` | `dashboard.html` | Sim | Página inicial autenticada. |
| GET | `/dashboard` | `dashboard` | `dashboard.html` | Sim | Dashboard. |
| GET | `/vendas` | `sales` | `sales/index.html` | `can_manage_sales` | Lista vendas. |
| GET/POST | `/vendas/nova` | `new_sale` | `sales/form.html` | `can_manage_sales` | Registra venda. |
| GET | `/vendas/<sale_id>` | `sale_detail` | `sales/detail.html` | `can_manage_sales` | Detalhe da venda. |
| GET | `/caixa` | `cash_register` | `cash_register.html` | `can_manage_cash_register` | Caixa atual e anteriores. |
| GET | `/caixa/<cash_register_id>` | `cash_register_detail` | `cash_register_detail.html` | `can_manage_cash_register` | Detalhes do caixa. |
| POST | `/caixa/abrir` | `open_cash_register_route` | - | `can_manage_cash_register` | Abre caixa. |
| POST | `/caixa/fechar` | `close_cash_register_route` | - | `can_manage_cash_register` | Fecha caixa com validação. |
| GET | `/relatorios` | `reports` | `reports/index.html` | `can_view_reports` | Relatórios e gráfico por período. |
| GET/POST | `/contas-a-pagar` | `payables` | `payables/index.html` | `can_manage_payables` | Lista e cadastra contas. |
| POST | `/contas-a-pagar/<payable_id>/pagar` | `pay_payable` | - | `can_manage_payables` | Marca conta como paga. |
| POST | `/contas-a-pagar/<payable_id>/reabrir` | `reopen_payable` | - | `can_manage_payables` | Reabre conta paga. |

## Templates e Interface

| Template | Função |
|---|---|
| `base.html` | Layout base com sidebar, topbar, notificações, mensagens flash, Bootstrap, CSS e JS. |
| `login.html` | Login e cadastro de nova adega. |
| `dashboard.html` | Tela inicial autenticada. |
| `master/companies.html` | Painel master para gerenciar adegas. |
| `subscription/activation.html` | Tela de ativação/regularização da assinatura. |
| `subscription/plans.html` | Tela estética de planos Basic e Pro. |
| `settings/index.html` | Configurações com abas de usuário, keys, equipe, financeiro, backup, importação, exportação, suporte e aparência. |
| `catalog/products.html` | Lista de produtos, filtros e edição expandida. |
| `catalog/product_form.html` | Formulário de produto. |
| `catalog/categories.html` | Lista, filtro, cadastro e edição de categorias. |
| `sales/index.html` | Histórico de vendas. |
| `sales/form.html` | Realização de venda. |
| `sales/detail.html` | Detalhe da venda finalizada. |
| `cash_register.html` | Caixa atual e caixas anteriores. |
| `cash_register_detail.html` | Detalhamento de caixa fechado. |
| `reports/index.html` | Relatórios e gráfico de vendas. |
| `payables/index.html` | Contas a pagar. |
| `errors/404.html` | Página de erro 404. |
| `errors/500.html` | Página de erro 500. |
| `placeholder.html` | Template auxiliar simples. |

## Arquivos Estáticos

| Arquivo | Função |
|---|---|
| `app/static/css/style.css` | Tema visual, layout responsivo, sidebar, cards, tabelas, formulários, vendas, caixa, relatórios, notificações e dark/light mode. |
| `app/static/js/main.js` | Tema light/dark, sidebar colapsável, abas, filtros avançados, autocomplete, moeda, kits, venda, pagamento, desconto e atalhos F2/F3. |

Não há imagens, logos ou ícones próprios no repositório. A interface usa texto, CSS e componentes Bootstrap.

## Segurança

O projeto já possui:

- login e logout com Flask-Login;
- senha armazenada com hash via Werkzeug;
- proteção de rotas com `@login_required`;
- permissões por usuário com `permission_required`;
- roles `master`, `admin` e `operator`;
- bloqueio por assinatura vencida;
- separação de dados por adega;
- consultas ORM/parametrizadas, reduzindo risco de SQL Injection;
- logs com proteção de campos sensíveis como senhas;
- `SECRET_KEY` configurável por variável de ambiente;
- verificação de e-mail no cadastro;
- troca de e-mail protegida por confirmação no e-mail antigo;
- recuperação de senha por token temporário;
- alertas críticos por e-mail com controle de envio duplicado;
- usuário inativo bloqueado;
- adega inativa bloqueada;
- login com limite de tentativas temporário;

### Pontos de atenção de segurança

- O `SECRET_KEY` padrão deve ser trocado em qualquer ambiente real.
- O app roda com `debug=True` em `app.py`; isso não deve ser usado em produção.
- Não há CSRF explícito nos formulários.
- Não há política de força de senha além de tamanho mínimo 3.
- Não há auditoria detalhada de alterações de dados.
- O `.env` não deve ser versionado com senhas reais.
- O usuário MySQL `root` não é recomendado em produção.

## Backup do MySQL

Backup é obrigatório para qualquer uso real. Como cada adega tem banco separado, faça backup do banco central e dos bancos das adegas.

O sistema possui uma aba **Backup** em `/configuracoes`, visível para usuários com acesso administrativo. Nessa aba é possível:

- escolher frequência `Somente manual`, `Diário`, `Semanal` ou `Mensal`;
- gerar um backup manual na hora;
- consultar último backup, status e nome do arquivo;
- salvar arquivos `.sql` na pasta `backups/`.

Além da interface, também é possível fazer backups pelo terminal com `mysqldump`.

Backup do banco central:

```bash
mysqldump -u root -p adega_central > backup_adega_central.sql
```

Backup de uma adega:

```bash
mysqldump -u root -p adega_4_adegajf > backup_adega_4_adegajf.sql
```

Restaurar:

```bash
mysql -u root -p adega_central < backup_adega_central.sql
```

Backup de todos os bancos:

```bash
mysqldump -u root -p --databases adega_central adega_1_painel_master adega_4_adegajf > backup_completo.sql
```

Recomendação: automatizar backup diário e manter cópia externa.

## Testes

Rodar todos os testes:

```bash
python -m unittest discover
```

Rodar arquivo específico:

```bash
python -m unittest tests.test_routes
```

Os testes usam configuração própria com SQLite em memória (`TESTING = True`) para validar rotas e regras sem depender do MySQL real.

Última validação completa:

```text
Ran 79 tests in 9.863s
OK
```

## Deploy Futuro

Para produção, o projeto pode evoluir para:

- servidor Linux;
- ambiente virtual isolado;
- banco MySQL gerenciado ou instalado no servidor;
- Gunicorn como servidor WSGI;
- Nginx como proxy reverso;
- domínio próprio;
- HTTPS com Let's Encrypt;
- serviço `systemd`;
- logs centralizados;
- backup automático;
- variáveis de ambiente separadas por ambiente;
- modo debug desativado;
- usuário MySQL dedicado;
- política de atualização e migração de banco.

Exemplo conceitual com Gunicorn:

```bash
gunicorn "app:create_app()" --bind 127.0.0.1:8000
```

Observação: o projeto ainda não possui arquivo de configuração Gunicorn, Dockerfile ou scripts de deploy.

## Evolução para SaaS

O sistema já possui bases importantes para SaaS:

- cadastro de empresas/adegas;
- banco separado por adega;
- usuários por empresa;
- permissões por usuário;
- painel master;
- assinatura/key;
- planos exibidos na interface;
- isolamento operacional por `company_id` e database.

Próximos passos para SaaS completo:

- onboarding comercial de clientes;
- cobrança real integrada;
- emissão automática de key/licença;
- domínio ou subdomínio por cliente;
- auditoria de ações;
- backup por cliente;
- painel financeiro do provedor;
- limites por plano;
- monitoramento de bancos das adegas;
- migrações versionadas por tenant;
- API para integrações externas;
- suporte multiusuário simultâneo em ambiente hospedado.

## Melhorias Recomendadas

### Técnicas

- Adotar Flask-Migrate/Alembic para migrações versionadas.
- Criar Dockerfile e `docker-compose.yml`.
- Desativar debug em produção.
- Adicionar CSRF nos formulários.
- Criar camada de services para regras de venda/estoque.
- Criar auditoria de alterações críticas.
- Melhorar testes de banco MySQL real.
- Criar comandos CLI para manutenção.
- Adicionar type hints em funções críticas.

### Produto

- Impressão de comprovante.
- Integração com maquininha.
- Integração WhatsApp.
- Cadastro de clientes.
- Histórico de movimentações de estoque.
- Sangria e suprimento de caixa.
- Cancelamento/estorno de venda.
- Dashboard financeiro.
- API JSON.
- Controle de produtos por código de barras com leitor físico.

## Status do Projeto

- [x] Login
- [x] Logout
- [x] Cadastro de nova adega pela tela de login
- [x] Usuário master do sistema
- [x] Painel master de adegas
- [x] Acesso do master a qualquer adega
- [x] Banco MySQL central
- [x] Banco MySQL separado por adega
- [x] Produtos
- [x] Categorias
- [x] Kits
- [x] Importação CSV/XLSX de produtos
- [x] Estoque mínimo
- [x] Notificação de estoque baixo
- [x] Abertura de caixa
- [x] Fechamento de caixa com validação
- [x] Vendas com múltiplos produtos
- [x] Múltiplas formas de pagamento
- [x] Desconto em reais
- [x] Troco e valor faltante
- [x] Baixa de estoque
- [x] Cálculo de lucro
- [x] Taxas de Pix/débito/crédito no lucro
- [x] Relatórios por período
- [x] Gráfico de vendas
- [x] Contas a pagar
- [x] Alertas de contas vencendo
- [x] Funcionários e permissões
- [x] Tema claro/escuro
- [x] Navbar colapsável
- [x] Logs de erro
- [x] Backup manual pela interface
- [x] Backup por período
- [x] Testes automatizados de rotas
- [ ] Migrações com Alembic
- [ ] Docker
- [ ] CSRF
- [ ] Impressão de comprovante
- [ ] Integração real com pagamento
- [ ] Deploy de produção
- [ ] Auditoria completa
- [ ] Cadastro de clientes
- [ ] Movimentações de estoque separadas

## Como Contribuir/Desenvolver

Fluxo recomendado:

1. Clonar o repositório.
2. Criar uma branch para a alteração.
3. Criar e ativar o ambiente virtual.
4. Instalar dependências.
5. Configurar MySQL local.
6. Criar/copiar `.env.example` para `.env`, se desejar.
7. Rodar o projeto localmente.
8. Rodar testes antes de finalizar.
9. Fazer commits claros e pequenos.

Comandos principais:

```bash
git checkout -b minha-alteracao
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
python -m unittest discover
```

## Licença

Este projeto ainda não possui uma licença definida.

## Autor

Desenvolvido por Rafael Borges Pontes  
Projeto Girofy

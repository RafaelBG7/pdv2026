# 07 - Front-end

## Visão Geral

O frontend é renderizado por templates Jinja2 no servidor e enriquecido por CSS customizado e JavaScript vanilla.

Arquivos principais:

- `app/templates/base.html`
- `app/templates/login.html`
- `app/templates/dashboard.html`
- `app/templates/catalog/*.html`
- `app/templates/sales/*.html`
- `app/templates/cash_register.html`
- `app/templates/reports/index.html`
- `app/templates/settings/index.html`
- `app/static/css/style.css`
- `app/static/js/main.js`

## Layout Base

Arquivo: `app/templates/base.html`.

Elementos:

- HTML em `pt-BR`.
- Bootstrap 5.3.3 via CDN.
- CSS local.
- Inicialização antecipada de tema antes do carregamento visual.
- Menu lateral para usuários autenticados.
- Topbar com alertas de estoque e nome do usuário.
- Flash messages Bootstrap.
- Bloco `{% block content %}`.
- JavaScript Bootstrap via CDN.
- JavaScript local.

## Navegação

Menu autenticado:

- Dashboard.
- Produtos.
- Categorias.
- Vendas.
- Caixa.
- Relatórios.
- Configurações.
- Sair.

Estado ativo calculado por `request.endpoint`.

## Tela de Login

Arquivo: `app/templates/login.html`.

Objetivo:

- Permitir login.
- Permitir cadastro de usuário.

Componentes:

- Card central.
- Abas Bootstrap: Entrar e Cadastrar.
- Formulário de login.
- Formulário de cadastro.

Validações visuais:

- Campos obrigatórios.
- Senha de cadastro com `minlength=6`.

Validações reais:

- No backend em `auth.login()`.

## Dashboard

Arquivo: `app/templates/dashboard.html`.

Objetivo:

- Tela inicial pós-login.
- Direcionar para venda se houver caixa aberto ou abertura de caixa se não houver.

Estado:

- Recebe `open_cash_register`.

Status:

- Parcial. Cards ainda têm textos de estrutura inicial e não trazem métricas reais.

## Produtos

Arquivos:

- `app/templates/catalog/products.html`.
- `app/templates/catalog/product_form.html`.

Funcionalidades:

- Busca por nome ou código de barras.
- Filtro por status.
- Filtros avançados por categoria, estoque e preço.
- Ordenação.
- Autocomplete de produtos e categorias.
- Lista em tabela com linha expansível.
- Edição rápida.
- Ativar/inativar.
- Excluir.
- Exibição de custo, venda, lucro e margem.
- Configuração de produto kit.

Eventos JavaScript:

- Autocomplete por `data-catalog-autocomplete`.
- Filtro avançado por `data-advanced-filter-toggle`.
- Máscara de moeda por `data-currency-input`.
- Exibição de campos de kit por `data-kit-toggle`.

## Categorias

Arquivo: `app/templates/catalog/categories.html`.

Funcionalidades:

- Criar categoria.
- Buscar categoria.
- Filtrar por uso: todas, com produtos, sem produtos.
- Ordenar por nome, quantidade de produtos ou criação.
- Editar em linha expansível.
- Excluir.

Regra visual:

- A tela permite acionar exclusão; o backend bloqueia se houver produto vinculado.

## Caixa

Arquivo: `app/templates/cash_register.html`.

Funcionalidades:

- Aba "Caixa atual".
- Aba "Caixas anteriores".
- Abertura de caixa com valor inicial.
- Exibição de status, abertura, valor inicial, vendas registradas, total vendido, valor esperado e lucro.
- Fechamento com valor final.
- Lista dos 10 últimos caixas fechados.

Validação real:

- O backend exige valor final igual ao esperado.

## Vendas

Arquivos:

- `app/templates/sales/index.html`.
- `app/templates/sales/form.html`.
- `app/templates/sales/detail.html`.

Lista:

- Exibe número da venda, data, total, formas de pagamento e ação de detalhe.

Formulário:

- Autocomplete de produto.
- Quantidade.
- Preço unitário somente leitura.
- Estoque somente leitura.
- Subtotal por linha.
- Adição e remoção de itens.
- Desconto em modal.
- Resumo da venda.
- Etapa de pagamentos.
- Valores de total, pago, falta e troco.

Atalhos:

- `F2`: abrir pagamento.
- `F3`: abrir desconto.
- `Escape`: fechar modal de desconto.

Detalhe:

- Produtos vendidos.
- Subtotal, desconto, total, lucro, pago e troco.
- Pagamentos utilizados.

## Relatórios

Arquivo: `app/templates/reports/index.html`.

Funcionalidades:

- Filtro por período.
- Datas inicial e final.
- Cards de resumo.
- Gráfico de barras em HTML/CSS.
- Tabela de vendas do período.
- Total por forma de pagamento.
- Produtos mais vendidos.

Períodos:

- Diário.
- Semanal.
- Mensal.
- Anual.
- Personalizado.

## Configurações

Arquivo: `app/templates/settings/index.html`.

Abas:

- Usuário.
- Suporte.
- Aparência.

Funcionalidades:

- Editar nome, sobrenome e telefone.
- Alterar email.
- Alterar senha.
- Exibir email mascarado.
- Alternar tema light/dark.

## Responsividade

Implementada em `style.css` com breakpoints:

- 1280px.
- 1080px.
- 900px.

Comportamentos:

- Menu lateral vira navegação superior em telas menores.
- Grids passam para 1 ou 2 colunas.
- Tabelas mantêm rolagem horizontal.
- Linha de venda se adapta para uma coluna.

## Integrações Externas

- Bootstrap CSS e JS via `https://cdn.jsdelivr.net`.

Risco:

- Sem internet, o Bootstrap via CDN pode não carregar. Para uso local offline, recomenda-se vendorizar os assets.

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

## Identidade Visual

Arquivo: `app/static/css/style.css`.

A interface usa tokens CSS em `:root` e `[data-theme='dark']` para manter a
identidade Girofy em tema claro e escuro.

Paleta atual:

- Roxo como cor principal da marca.
- Ciano como cor de destaque para ações, foco, sidebar e gradientes.
- Verde para sucesso, ativo, pago, aberto e picos positivos.
- Âmbar para avisos e pendências.
- Vermelho para erro, perigo, inativo, fechado e vencido.
- Azul para informação e estados neutros.

Componentes que herdam esses tokens:

- Botões principais.
- Sidebar e item ativo.
- Avatar/menu do usuário.
- Badges de status.
- Cards, tabelas, formulários e painéis.
- Gráfico de relatórios e destaque de pico.
- Alertas de assinatura e contas a pagar.

## Navegação

Menu autenticado:

- Dashboard.
- Produtos.
- Categorias.
- Vendas.
- Caixa.
- Relatórios.
- Estoque.
- Auditoria.
- Configurações.
- Sair.

Estado ativo calculado por `request.endpoint`.

## Tela de Login

Arquivo: `app/templates/login.html`.

Objetivo:

- Permitir login.
- Permitir cadastro de usuário.

Componentes:

- Card central com wrapper responsivo próprio.
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
- Exibir visão operacional do dia.
- Direcionar rapidamente para venda, produtos, caixa e relatórios.

Estado:

- Recebe `open_cash_register`.

Status:

- Implementado com resumo operacional, produtos de maior movimento, estoque baixo, contas a pagar e botão `Realizar Venda - F3`.

## Produtos

Arquivos:

- `app/templates/catalog/products.html`.
- `app/templates/catalog/product_form.html`.

Funcionalidades:

- Busca por nome ou código de barras.
- Menu lateral de categorias: Todas + categorias da adega, com coluna própria e nomes longos limitados a duas linhas.
- Filtro por status.
- Filtros avançados por categoria, estoque e preço.
- Ordenação.
- Autocomplete de produtos e categorias.
- Barra principal de busca/filtros em linha única com rolagem horizontal controlada em telas estreitas.
- Placeholders de busca no padrão `Buscar X`, como `Buscar produto` e `Buscar categoria`.
- Lista em tabela com linha expansível.
- Edição rápida.
- Ativar/inativar.
- Excluir.
- Exibição de custo, venda, lucro e margem.
- Configuração de produto kit.
- Campo de motivo quando a alteração muda o saldo de estoque.

Comportamento visual:

- A coluna lateral de categorias usa largura responsiva entre `220px` e `300px`.
- Cada categoria usa grade interna com nome flexível e contador fixo à direita.
- Nomes longos quebram com limite de duas linhas para evitar corte horizontal.
- Em telas menores, o menu de categorias deixa de ser lateral e passa a ocupar a largura disponível.

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
- Caixa atual com total por forma de pagamento, total geral, quantidade de vendas e ticket médio.
- Linha do tempo expansível das vendas do caixa atual.
- Fechamento com valor final.
- Lista dos 10 últimos caixas fechados em linhas resumidas e expansíveis.
- Análise completa do caixa com linha do tempo cronológica de vendas.

Validação real:

- O backend exige valor final igual ao esperado.

## Vendas

Arquivos:

- `app/templates/sales/index.html`.
- `app/templates/sales/form.html`.
- `app/templates/sales/detail.html`.

Lista:

- Exibe número da venda, data, vendedor, total, formas de pagamento, status, caixa e ação de detalhe.
- Exibe por padrão apenas vendas do dia atual.
- Filtros por coluna no frontend sem recarregar a página.
- Campo de venda usa `Buscar venda`.
- Filtros de vendedor, pagamento e status usam listas visuais clicáveis com opção `Todos`.
- Filtro de total usa `Buscar valor` e ordenação maior/menor.

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
- `F3` em Dashboard, Vendas e Caixa: abrir a tela de registrar venda.
- `F3` dentro da venda: abrir desconto.
- Na tela pós-venda, `Enter`, `Espaço` e `F3` abrem uma nova venda.
- Atalhos globais não são disparados durante digitação em inputs, selects ou áreas editáveis.
- `Escape`: fechar modal de desconto.

Detalhe:

- Produtos vendidos.
- Subtotal, desconto, total, lucro, pago e troco.
- Pagamentos utilizados.

## Estoque

Arquivos:

- `app/templates/stock/movements.html`.
- `app/templates/stock/form.html`.

Funcionalidades:

- Lista de movimentações com filtros por produto, categoria, tipo, usuário e período.
- Cards de resumo com entradas, saídas e produtos movimentados.
- Entrada manual de estoque.
- Ajuste manual por saldo final ou diferença.
- Prévia de saldo atual e saldo resultante no formulário.
- Linhas expansíveis para ver origem, motivo, observações e custo.

Comportamento visual:

- Filtros organizados em grade de quatro colunas no desktop.
- Datas e botões seguem a mesma altura dos demais campos.
- Botões `Filtrar` e `Limpar` ficam alinhados e não quebram texto.
- Em resoluções menores, a grade passa para duas colunas e depois uma coluna.

## Auditoria

Arquivos:

- `app/templates/audit/index.html`.
- `app/templates/audit/master.html`.
- `app/templates/audit/_table.html`.

Funcionalidades:

- Lista de eventos por data, ação, entidade, usuário e método.
- Busca por texto.
- Filtro por usuário, ação, entidade e período.
- Linhas expansíveis com valores antigos e novos.
- Versão operacional por adega e versão central para master.

Comportamento visual:

- Filtros usam grade alinhada em quatro colunas na auditoria da adega.
- A auditoria master usa grade de três colunas.
- Campos de data usam tamanho de fonte responsivo para evitar corte do calendário.
- Botões e selects respeitam largura máxima do card, evitando estouro lateral.

## Relatórios

Arquivo: `app/templates/reports/index.html`.

Funcionalidades:

- Alternância entre "Resumo geral" e "Por produto".
- Filtro por período.
- Datas inicial e final.
- Cards de resumo.
- Gráfico de barras em HTML/CSS.
- Alternância entre faturamento e quantidade no gráfico diário.
- Destaque visual e tooltip do horário de pico.
- Resumo do pico por quantidade e por faturamento.
- Tabela de vendas do período.
- Total por forma de pagamento.
- Produtos mais vendidos.
- Relatório por produto com categoria, quantidade vendida, faturamento, custo, lucro, ticket médio e estoque atual.
- Filtros por produto: data inicial, data final, categoria, produto e ordenação.

Períodos:

- Diário.
- Semanal.
- Mensal.
- Anual.
- Personalizado.

O gráfico diário usa 24 colunas responsivas e reduz apenas a quantidade de rótulos visíveis
em telas estreitas; todas as horas continuam acessíveis por foco ou ponteiro.

## Configurações

Arquivo: `app/templates/settings/index.html`.

Abas:

- Usuário.
- Equipe.
- Financeiro.
- Backup.
- Importação.
- Suporte.
- Aparência.

Funcionalidades:

- Editar nome, sobrenome e telefone.
- Alterar email.
- Alterar senha.
- Exibir email mascarado.
- Buscar funcionário com placeholder `Buscar funcionário`.
- Contratar funcionário e ajustar perfil funcionário/gerente/admin.
- Configurar taxas de maquininha/Pix.
- Rodar backup manual e configurar frequência.
- Importar produtos por planilha e baixar modelo.
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
- Barras críticas de filtros evitam quebra de texto com grids responsivos por card.
- Auditoria e estoque priorizam alinhamento em múltiplas linhas em vez de comprimir todos os controles em uma linha.
- Menu lateral de categorias de produtos evita corte de nomes longos com quebra controlada.
- Linha de venda se adapta para uma coluna.
- Linhas expansíveis usam o mesmo comportamento em produtos, caixas, estoque e auditoria.

## Integrações Externas

- Bootstrap CSS e JS via `https://cdn.jsdelivr.net`.

Risco:

- Sem internet, o Bootstrap via CDN pode não carregar. Para uso local offline, recomenda-se vendorizar os assets.

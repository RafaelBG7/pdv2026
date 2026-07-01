# 18 - Casos de Uso

## UC001 - Realizar Login

Ator: usuário.

Objetivo: acessar o sistema.

Pré-condições:

- Usuário cadastrado.

Fluxo principal:

1. Usuário acessa `/login`.
2. Informa usuário e senha.
3. Sistema valida credenciais.
4. Sistema autentica sessão.
5. Sistema redireciona para dashboard.

Fluxo alternativo:

- Usuário já autenticado acessa `/login`; sistema redireciona para dashboard.

Exceções:

- Usuário ou senha inválidos.

Pós-condições:

- Usuário autenticado.

## UC002 - Cadastrar Produto

Ator: usuário autenticado.

Objetivo: adicionar produto ao catálogo.

Pré-condições:

- Usuário autenticado.

Fluxo principal:

1. Acessa Produtos.
2. Clica em Novo produto.
3. Informa nome, código, categoria, custo, venda, estoque e status.
4. Sistema valida nome e código único.
5. Sistema salva produto.
6. Sistema retorna para listagem.

Fluxo alternativo:

- Produto kit: usuário marca Kit, informa produto base e unidades descontadas.

Exceções:

- Nome ausente.
- Código duplicado.
- Kit sem base ou quantidade.

Pós-condições:

- Produto disponível no catálogo.

## UC003 - Abrir Caixa

Ator: operador.

Objetivo: iniciar turno de vendas.

Pré-condições:

- Usuário autenticado.
- Não existir caixa aberto.

Fluxo principal:

1. Acessa Caixa.
2. Informa valor inicial.
3. Sistema cria caixa com status `open`.
4. Sistema libera venda.

Exceções:

- Já existe caixa aberto.

Pós-condições:

- Caixa aberto.

## UC004 - Registrar Venda

Ator: operador.

Objetivo: vender produtos e baixar estoque.

Pré-condições:

- Usuário autenticado.
- Caixa aberto.
- Produtos ativos cadastrados.
- Estoque suficiente.

Fluxo principal:

1. Acessa Nova Venda.
2. Seleciona produtos.
3. Informa quantidades.
4. Aplica desconto opcional.
5. Informa uma ou mais formas de pagamento.
6. Sistema valida estoque.
7. Sistema valida pagamento.
8. Sistema cria venda, itens e pagamentos.
9. Sistema baixa estoque.
10. Sistema exibe detalhe da venda.

Fluxo alternativo:

- Pagamento maior que total: sistema calcula troco.

Exceções:

- Sem caixa aberto.
- Sem produto válido.
- Estoque insuficiente.
- Pagamento insuficiente.
- Kit sem configuração.

Pós-condições:

- Venda registrada.
- Estoque atualizado.
- Caixa acumula total vendido.

## UC005 - Fechar Caixa

Ator: operador.

Objetivo: encerrar caixa do turno.

Pré-condições:

- Caixa aberto.

Fluxo principal:

1. Acessa Caixa.
2. Confere valor esperado.
3. Informa valor final.
4. Sistema compara valor final com esperado.
5. Sistema fecha caixa.

Exceções:

- Valor final menor que esperado.
- Valor final maior que esperado.
- Não há caixa aberto.

Pós-condições:

- Caixa fechado.

## UC006 - Consultar Relatório

Ator: gerente ou administrador futuro.

Objetivo: acompanhar vendas e lucro.

Pré-condições:

- Usuário autenticado.
- Vendas registradas.

Fluxo principal:

1. Acessa Relatórios.
2. Seleciona período.
3. Sistema busca vendas no intervalo.
4. Sistema calcula totais.
5. Sistema exibe gráfico, tabela, pagamentos e produtos.

Fluxo alternativo:

- Período personalizado com data final menor que inicial: sistema inverte datas.

Exceções:

- Nenhuma venda no período.

Pós-condições:

- Informações gerenciais exibidas.

## UC007 - Alterar Senha

Ator: usuário autenticado.

Objetivo: atualizar credencial.

Pré-condições:

- Usuário autenticado.

Fluxo principal:

1. Acessa Configurações.
2. Informa senha atual.
3. Informa nova senha e confirmação.
4. Sistema valida senha atual.
5. Sistema valida tamanho e confirmação.
6. Sistema grava novo hash.

Exceções:

- Senha atual incorreta.
- Nova senha curta.
- Confirmação divergente.

Pós-condições:

- Senha alterada.

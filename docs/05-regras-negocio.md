# 05 - Regras de Negócio

## Autenticação

- Usuário autenticado não acessa novamente `/login`; é redirecionado para `/dashboard`.
- Usuário anônimo é redirecionado para login ao acessar rotas com `@login_required`.
- Login usa `username` e `password`.
- Senhas são conferidas com hash Werkzeug.
- Cadastro exige usuário, senha com pelo menos 6 caracteres e confirmação igual.
- Cadastro cria usuário com `role='admin'`.
- Usuário inicial `admin/admin123` é criado automaticamente se não existir.

## Usuário e Configurações

- Nome, sobrenome e telefone podem ser editados pelo usuário conectado.
- Email pode ser alterado sem confirmação.
- Senha só pode ser alterada informando a senha atual.
- Nova senha deve ter pelo menos 6 caracteres.
- Confirmação da nova senha deve coincidir.

## Produtos

- Produto deve ter nome.
- Código de barras é opcional, mas se informado deve ser único.
- Preço de custo, preço de venda e estoque são normalizados para valores não negativos.
- Produto ativo aparece como vendável.
- Produto inativo não é selecionado na venda.
- Produto pode ser ativado/inativado.
- Produto pode ser excluído fisicamente.
- Lucro unitário é `sale_price - cost_price`.
- Margem é calculada sobre o preço de venda.

## Kits

- Produto kit deve informar produto base e quantidade de baixa.
- Produto kit não pode usar a si mesmo como produto base.
- Estoque efetivo do kit é `estoque_produto_base // quantidade_por_kit`.
- Venda de kit baixa estoque do produto base, não do produto kit.
- Kit sem configuração válida não pode ser vendido.
- Kit exige estoque suficiente no produto base.

## Categorias

- Categoria deve ter nome.
- Nome da categoria deve ser único.
- Categoria pode ser filtrada por busca, uso e ordenação.
- Categoria com produto vinculado não pode ser excluída.

## Caixa

- Só pode haver um caixa aberto por vez.
- Venda só pode ser registrada com caixa aberto.
- Abertura registra valor inicial e usuário.
- Fechamento exige informar valor final.
- Valor esperado para fechamento é `valor_inicial + total_vendido_no_caixa`.
- Se valor final for menor que o esperado, o fechamento é bloqueado e o sistema informa falta.
- Se valor final for maior que o esperado, o fechamento é bloqueado e o sistema informa excedente.
- Fechamento correto define `closed_at`, `closing_amount` e `status='closed'`.

## Venda

- Venda exige pelo menos um produto válido.
- Quantidade deve ser maior que zero.
- Produto deve existir e estar ativo.
- Estoque deve ser suficiente antes da venda ser gravada.
- Subtotal é soma de `sale_price * quantity`.
- Desconto não pode ultrapassar subtotal; é limitado por `min(desconto, subtotal)`.
- Total final é `subtotal - desconto`.
- Pagamento total deve ser maior ou igual ao total final.
- Pagamento menor bloqueia a venda e preserva estado do formulário.
- Pagamento maior gera troco.
- Venda finalizada recebe `payment_status='paid'`.
- Itens gravam preço de venda e custo do momento da venda.
- Lucro do item é `(unit_price - unit_cost_price) * quantity`.
- Lucro da venda é soma dos lucros dos itens menos desconto.
- Após gravar a venda, o estoque é baixado.

## Formas de Pagamento

Métodos implementados:

- `money`: Dinheiro.
- `pix`: Pix.
- `debit`: Débito.
- `credit`: Crédito.

Uma venda pode ter uma ou mais formas de pagamento, desde que o total pago cubra o valor final.

## Relatórios

- Período diário usa a data atual ou data inicial informada.
- Período semanal usa últimos 7 dias.
- Período mensal usa últimos 30 dias.
- Período anual usa últimos 365 dias.
- Período personalizado aceita data inicial e final; se final for menor que inicial, o sistema inverte.
- Relatório calcula: quantidade de vendas, itens, subtotal, descontos, total final, lucro e ticket médio.
- Produtos mais vendidos são ordenados por total vendido.

## Alertas

- Produtos ativos com estoque efetivo menor ou igual a 5 geram alerta.
- Produtos zerados exibem mensagem de sem estoque.
- Apenas os 10 primeiros alertas são exibidos.
- Alertas são ordenados por quantidade e nome.

## Regras Planejadas ou Ausentes

- Administrador exclusivo para excluir produtos.
- Controle por perfil.
- Logs de auditoria.
- Histórico de movimentação de estoque.
- Cancelamento ou estorno de venda.
- Sangria e reforço de caixa.
- Recuperação de senha.
- Bloqueio de usuário inativo.

# 05 - Regras de Negócio

## Autenticação e Cadastro

- Usuário anônimo é redirecionado para login ao acessar rota protegida.
- Login usa `username` e `password`.
- Senhas são armazenadas e conferidas com hash Werkzeug.
- Usuário inativo não deve operar o sistema.
- Usuário `master` do sistema acessa o painel master.
- Cadastro cria uma empresa/adega e o primeiro usuário como `admin`.
- Cadastro pode receber uma key válida ou marcar "Não tenho key".
- Cadastro sem key é permitido, mas a adega fica bloqueada para operação.
- Cada nova adega deve ter seu banco MySQL operacional próprio.
- O usuário inicial global usa `MASTER_DEFAULT_USERNAME` e `MASTER_DEFAULT_PASSWORD`; em produção a senha padrão `master123` é recusada.

## Assinatura e Key

- Key é gerada pelo master do sistema.
- Key pode ser avulsa ou vinculada a uma adega.
- Key possui plano e data de validade.
- Key usada fica vinculada à empresa.
- Adega sem key, vencida ou inativa é redirecionada para `/assinatura`.
- Planos Basic e Pro existem como estrutura comercial inicial, sem cobrança real integrada.

## Usuário e Configurações

- Usuário pode editar nome, sobrenome, telefone, email e senha.
- Senha só pode ser alterada informando a senha atual.
- Funcionário comum não vê equipe, financeiro, plano, importação ou exportação.
- Admin da adega pode contratar e editar funcionários.
- CPF duplicado é bloqueado dentro da mesma adega.
- Pode existir mais de um admin por adega.

## Produtos

- Produto deve ter nome.
- Código de barras é opcional, mas não pode duplicar dentro da mesma adega.
- Preço de custo, preço de venda e estoque são normalizados para valores não negativos.
- Produto ativo aparece como vendável.
- Produto inativo não deve ser vendido.
- Produto possui estoque mínimo para alerta.
- Lucro unitário base é `sale_price - cost_price`.
- Taxas de Pix/débito/crédito podem reduzir o lucro final conforme configuração.
- Produto criado com estoque inicial maior que zero gera movimentação `initial_stock`.
- Edição de estoque em formulário ou linha rápida gera `adjustment_in` ou `adjustment_out`.
- Ajuste de estoque exige motivo.

## Kits

- Produto kit é opcional.
- Kit deve informar produto base e quantidade consumida.
- Kit não pode usar a si mesmo como produto base.
- Estoque efetivo do kit é `estoque_produto_base // quantidade_por_kit`.
- Venda de kit baixa estoque do produto base.
- Kit sem configuração válida não pode ser vendido.

## Categorias

- Categoria deve ter nome.
- Nome da categoria é único dentro da adega atual.
- Adegas diferentes podem usar o mesmo nome de categoria.
- Categoria com produto vinculado não pode ser excluída.

## Caixa

- Só pode haver um caixa aberto por vez na adega.
- Venda só pode ser registrada com caixa aberto.
- Abertura registra valor inicial e usuário.
- Fechamento exige informar valor final.
- Valor esperado é `valor_inicial + total_vendido_no_caixa`.
- Se valor final for menor, o sistema informa quanto falta.
- Se valor final for maior, o sistema informa quanto excedeu.
- Fechamento só conclui quando o valor bate exatamente.
- Caixa atual exibe totais por forma de pagamento, total geral, quantidade de vendas e ticket médio para usuários autorizados a ver relatórios.
- A análise do caixa usa linha do tempo cronológica das vendas, com itens e pagamentos expansíveis.

## Venda

- Venda exige pelo menos um produto válido.
- Quantidade deve ser maior que zero.
- Produto deve existir, estar ativo e pertencer à adega.
- Estoque pode ser bloqueante ou não conforme configuração da adega.
- Quando `allow_negative_stock` está ativo, a venda pode finalizar com estoque zerado/negativo e o sistema baixa normalmente para valor negativo.
- Kits continuam exigindo componente base válido e quantidade configurada.
- Pedido não deve ser resetado quando houver erro.
- Desconto em reais não pode ultrapassar o subtotal.
- Total final é `subtotal - desconto`.
- Pagamento total deve ser maior ou igual ao total final.
- Pagamento maior gera troco.
- Venda pode ter dinheiro, Pix, débito e crédito juntos.
- Itens gravam preço e custo do momento da venda.
- Venda finalizada baixa estoque por meio do serviço de estoque.
- Cada item da venda gera movimentação `sale`; kits movimentam o produto base.
- Venda, itens, pagamentos, estoque e movimentações são gravados na mesma transação.
- Se a baixa de qualquer item falhar, a venda inteira é revertida.
- A listagem principal em `/vendas` mostra o histórico do dia atual; relatórios continuam disponíveis para períodos maiores.
- Filtros de venda por vendedor, pagamento e status aparecem como listas visuais clicáveis.
- Atalho `F2` abre/conclui finalização.
- Em Dashboard, Vendas e Caixa, `F3` inicia uma nova venda quando o foco não está em um campo.
- Na tela de registrar venda, `F3` abre o desconto e não recarrega a página.
- Na tela pós-venda, `Enter`, `Espaço` e `F3` iniciam uma nova venda quando o foco não está em um campo.

## Importação e Exportação

- Importação de produtos fica em Configurações > Importação.
- Apenas dono/admin autorizado da adega deve importar.
- Planilha aceita CSV/XLSX.
- Categoria é criada se não existir na adega.
- Produto existente é atualizado quando identificado pelo nome.
- Estoque importado gera movimentação `import` para produto novo ou ajuste do existente.
- Exportação fica em Configurações > Exportação.
- Apenas admin/master deve exportar dados.

## Movimentação de Estoque

- `products.stock_quantity` é o saldo atual.
- `stock_movements` é o histórico rastreável.
- Nenhuma operação deve alterar saldo sem registrar movimentação.
- Entradas manuais usam `entry`.
- Ajustes positivos usam `adjustment_in`.
- Ajustes negativos usam `adjustment_out`.
- Cadastro inicial usa `initial_stock`.
- Importação usa `import`.
- Venda usa `sale`.
- Quantidade da movimentação é sempre positiva; o tipo define entrada ou saída.
- A tela `/estoque/movimentacoes` permite filtrar por produto, categoria, tipo, usuário e período.

## Auditoria

- Ações críticas gravam registro em `audit_logs`.
- O registro inclui usuário, perfil, rota, método, IP, user-agent, request id, entidade e valores sanitizados.
- Campos sensíveis são mascarados antes de persistir.
- Auditoria operacional fica isolada por adega.
- O master do sistema acessa auditoria central em `/master/auditoria`.
- Eventos cobertos incluem login, logout, key, assinatura, produtos, categorias, importação, exportação, caixa, venda, contas a pagar e estoque.

## Relatórios

- Diário usa a data atual por padrão.
- Semanal usa últimos 7 dias.
- Mensal usa últimos 30 dias.
- Anual usa últimos 365 dias.
- Personalizado usa datas escolhidas.
- Relatório calcula vendas, descontos, total, lucro, ticket médio, pagamentos e produtos mais vendidos.
- No período diário, vendas são agrupadas no banco em intervalos de uma hora, das 00h às 23h.
- O pico por quantidade e o pico por faturamento são calculados separadamente.
- Horas sem venda permanecem no gráfico com valor zero.
- Relatório por produto usa agregação no banco por itens vendidos no período.
- Relatório por produto mostra quantidade vendida, faturamento, custo total, lucro estimado, ticket médio e estoque atual.
- Relatório por produto pode ser filtrado por período, categoria e produto específico.
- Relatório por produto pode ordenar por mais vendidos, maior faturamento, maior lucro, menor estoque e produtos sem venda.

## Notificações

- Produto sem estoque gera alerta.
- Produto com estoque igual ou abaixo do mínimo gera alerta.
- Conta vencida gera alerta.
- Conta vencendo hoje gera alerta.
- Conta vencendo em até 3 dias gera alerta.
- Notificações pertencem à adega atual.

## Pendências de Negócio

- Cancelamento/estorno de venda.
- Sangria e reforço de caixa.
- Fornecedores e compras.
- Cobrança real de assinatura.

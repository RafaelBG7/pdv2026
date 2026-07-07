# 21 - Glossário

## Girofy

Nome do sistema e da operação representada pelo PDV.

## PDV

Ponto de venda. No projeto, é o conjunto de telas e regras para registrar vendas, pagamentos e baixa de estoque.

## Caixa

Controle financeiro de um turno. Possui valor inicial, vendas vinculadas, valor esperado e valor final.

## Caixa Aberto

Caixa com `status='open'`. É obrigatório para registrar venda.

## Caixa Fechado

Caixa com `status='closed'`, `closed_at` preenchido e `closing_amount` registrado.

## Valor Inicial

Dinheiro informado na abertura do caixa.

## Valor Esperado

Soma do valor inicial com o total vendido no caixa.

## Produto

Item cadastrado para venda ou controle de estoque.

## Produto Ativo

Produto disponível para venda e listagem padrão.

## Produto Inativo

Produto mantido no cadastro, mas indisponível para venda.

## Código de Barras

Campo único opcional usado para identificar produto.

## Categoria

Agrupamento de produtos.

## Kit

Produto composto que baixa estoque de outro produto base. Exemplo: caixa com 8 unidades que desconta 8 unidades de um item unitário.

## Produto Base

Produto usado como origem de estoque para um kit.

## Estoque Efetivo

Quantidade vendável. Para produto normal, é o estoque físico. Para kit, é `estoque do produto base // quantidade por kit`.

## Venda

Registro de transação comercial, com itens, desconto, pagamentos e vínculo ao caixa.

## Item de Venda

Linha de produto dentro de uma venda, com quantidade, preço unitário, custo unitário, total e lucro.

## Pagamento

Valor pago em uma forma de pagamento.

## Formas de Pagamento

Métodos atuais:

- Dinheiro.
- Pix.
- Débito.
- Crédito.

## Subtotal

Soma dos itens antes do desconto.

## Desconto

Valor abatido do subtotal. Não pode superar o subtotal.

## Total Final

Subtotal menos desconto.

## Troco

Valor pago acima do total final.

## Lucro

No item: diferença entre preço de venda e custo, multiplicada pela quantidade.

Na venda: soma dos lucros dos itens menos desconto.

## Ticket Médio

Total vendido dividido pela quantidade de vendas no período.

## Flash Message

Mensagem temporária exibida ao usuário após ações ou validações.

## Blueprint

Mecanismo do Flask para organizar rotas por módulo.

## Template

Arquivo Jinja2 usado para renderizar HTML.

## ORM

Mapeamento objeto-relacional. No projeto, SQLAlchemy/Flask-SQLAlchemy.

## Migração Manual

Função que executa `ALTER TABLE` diretamente na inicialização para adicionar colunas ausentes. É uma solução provisória.

## Auditoria

Registro histórico de ações críticas. Não implementada atualmente.

## CSRF

Ataque de falsificação de requisição. Proteção específica ainda não implementada.

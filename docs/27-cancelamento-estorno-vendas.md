# Cancelamento e estorno de vendas — Web, API e Windows

## Objetivo e terminologia

O Girofy implementa **cancelamento lógico** de venda. A venda, seus itens e seus pagamentos
nunca são apagados. “Estorno”, neste documento, significa invalidar a venda para os totais
operacionais e devolver o estoque; não significa executar automaticamente uma devolução junto
à adquirente, banco ou Pix.

## Regra central

Uma venda concluída passa de `completed` para `cancelled` e recebe:

- data/hora (`cancelled_at`);
- usuário responsável (`cancelled_by_user_id`);
- motivo obrigatório de até 500 caracteres (`cancellation_reason`).

A operação é atômica: mudança de status, devolução de estoque e auditoria são confirmadas
juntas. Qualquer falha desfaz tudo. Uma segunda tentativa retorna conflito e não movimenta o
estoque novamente.

## Estoque e kits

A devolução usa as movimentações originais da venda (`source_type=sale`) como fonte da verdade.
Assim, um kit devolve exatamente o componente e a quantidade baixados no momento da venda,
mesmo que a composição do kit tenha sido alterada depois. A contrapartida usa:

- `movement_type=cancellation`;
- `source_type=sale_cancellation`;
- `source_id=<id da venda>`;
- estoque anterior e posterior, usuário, motivo e observação.

Vendas legadas sem movimentação original não são canceladas automaticamente: o sistema
interrompe a operação para não adivinhar uma recomposição e corromper o estoque.

## Financeiro, relatórios e caixa

Pagamentos permanecem gravados para conciliação e auditoria. Vendas canceladas não entram em
dashboard, relatórios, rankings, lucro, ticket médio nem totais de caixa aberto.

Se o cancelamento ocorrer depois do fechamento, a conferência original do caixa fica imutável.
O sistema exibe separadamente a quantidade e o valor cancelados e o novo total válido. Isso
evita reescrever silenciosamente um fechamento que já foi contado e informado pelo operador.

## Permissão

A permissão é `can_cancel_sales`. Administradores têm autorização pelo papel administrativo.
Gerentes recebem a permissão no padrão atual; operadores precisam recebê-la explicitamente em
Configurações. A autorização é validada no servidor — ocultar o botão na interface é apenas uma
proteção adicional de UX.

## Versão Web

1. Abra **Vendas** e selecione uma venda.
2. Clique em **Cancelar venda**.
3. Informe o motivo e confirme no modal.
4. A página recarrega com o selo **Cancelada**, autoria, data e motivo.

O formulário usa `POST`, proteção CSRF e a rota
`POST /vendas/<sale_id>/cancelar`. A listagem mantém a venda visível para consulta histórica.

## API v1

### `POST /api/v1/sales/<sale_id>/cancel`

Requer Bearer token e `can_cancel_sales`.

```json
{
  "reason": "Cliente desistiu antes de retirar."
}
```

A resposta inclui a venda com `status`, metadados do cancelamento, movimentos de devolução e
`cash_register_was_closed`. Erros relevantes: `permission_denied`,
`cancellation_reason_required`, `sale_not_found`, `sale_already_cancelled`,
`sale_stock_movements_missing` e `sale_cancellation_audit_failed`.

## Aplicativo Windows

Na aba **Vendas**, expanda uma linha e clique em **Cancelar venda**. Um modal nativo solicita o
motivo e mantém a interface responsiva durante a chamada assíncrona. Após sucesso, o histórico
é atualizado e a venda mostra o estado **CANCELADA**, com motivo, usuário e data. O botão não é
exibido sem permissão ou para uma venda já cancelada.

Na aba **Caixa**, a linha do tempo continua mostrando lançamentos cancelados para rastreabilidade.
Caixas fechados recebem o indicador de ajuste posterior sem alterar os números originais.

## Auditoria e segurança

O evento `sale_cancelled` registra empresa, usuário, venda, status anterior e novo, motivo,
caixa, movimentos de estoque, IP, user-agent, rota, método HTTP e request-id. A criação desse
registro é obrigatória: se ela falhar, toda a transação é revertida.

O carregamento da venda sempre filtra `company_id`; portanto, um usuário não consegue consultar
ou cancelar uma venda de outra empresa. Em MySQL, a venda é bloqueada durante a transação para
serializar tentativas concorrentes.

## Limites atuais

- Não há integração automática de estorno com adquirente, banco ou Pix.
- Não há cancelamento parcial por item; o cancelamento é da venda inteira.
- Venda legada sem trilha original de estoque exige correção administrativa antes do cancelamento.

## Cobertura automatizada

Os testes de rota/API verificam cancelamento normal, recomposição exata de kit, preservação de
itens e pagamentos, movimento de cancelamento, auditoria única, recusa da segunda tentativa,
exclusão dos relatórios, autorização explícita e isolamento entre empresas. A suíte de regressão
existente continua cobrindo venda multiproduto, caixa, lucro, ticket médio, estoque, permissões,
API e multiadega; toda ela deve permanecer verde antes da publicação.

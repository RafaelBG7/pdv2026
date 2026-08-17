# Backend e regras compartilhadas

Estado detalhado e critérios de continuidade: [31-estado-atual-17-08-2026.md](../31-estado-atual-17-08-2026.md).

O backend Flask/MySQL é a fonte de verdade para Web e Windows. `app/services` concentra regras de venda, caixa, estoque, catálogo, dashboard, autenticação, auditoria, alertas e notificações. `app/routes/api/v1.py` expõe contratos ao WPF; as rotas HTML chamam os mesmos serviços nas operações críticas.

## Garantias

- transações e rollback atômico;
- dinheiro com `Decimal` nas decisões críticas;
- idempotência de vendas por empresa;
- locks para estoque/caixa em banco compatível;
- filtro e sessão por tenant;
- permissão verificada no servidor;
- auditoria com origem Web/Windows;
- erros API com código, mensagem, status e campo;
- rate limit Redis e health checks;
- migrations Alembic separadas para central e tenants.

O cliente nunca deve acessar MySQL diretamente. Novas regras compartilhadas precisam de testes de sucesso, erro, repetição, concorrência aplicável e isolamento entre empresas.

## Serviços que devem permanecer centralizados

- venda, pagamentos, desconto, lucro e idempotência;
- caixa, saldo esperado, abertura e fechamento;
- estoque, kits, baixa, ajuste e estorno;
- autenticação, tokens e recuperação de senha;
- permissões e seleção de tenant;
- auditoria, notificações e e-mail;
- catálogo, dashboard, relatórios e contas;
- migrations, health checks e rate limit.

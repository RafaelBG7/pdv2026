# Girofy Web

A Web é a interface administrativa e operacional mais ampla. Usa Flask-Login, templates Jinja, CSS/JavaScript e o banco tenant selecionado pelo backend.

## Funções

- onboarding, confirmação de e-mail, login e recuperação de senha;
- dashboard, produtos, categorias, vendas, caixa, estoque, contas e relatórios;
- auditoria, equipe, permissões, importação, exportação e backup;
- configurações operacionais, financeiras, alertas, acessibilidade e tema;
- painel master SaaS, empresas, ativações, assinaturas e logs.

As telas podem validar formato para resposta rápida, mas venda, caixa e estoque são confirmados exclusivamente pelos serviços do servidor. A sessão e a empresa ativa nunca substituem o filtro `company_id`/sessão tenant.

Arquivos principais: `app/routes`, `app/templates` e `app/static`. Consulte [paridade](../FEATURE_PARITY.md) para saber o que também existe no Windows.

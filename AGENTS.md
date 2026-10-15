@RTK.md

## Regra obrigatoria de entrega

- Toda alteracao deve ser preparada e publicada primeiro em homologacao (`develop`).
- Depois do deploy em homologacao, a alteracao deve ser testada manualmente nesse ambiente.
- E proibido promover, fazer deploy, merge ou qualquer alteracao em producao (`main`) sem autorizacao explicita do usuario, concedida depois do teste manual em homologacao.
- A autorizacao nao pode ser presumida a partir do pedido original de implementacao, de um commit, de um push ou da aprovacao de testes automatizados.
- Somente apos essa autorizacao, promover a mesma alteracao validada para producao e gerar a nova versao correspondente.
- Se ainda nao houver autorizacao, encerrar o trabalho com homologacao pronta/testada e informar que a promocao para producao e a nova versao estao pendentes.


## Orientações verificáveis de manutenção

- Leia [a auditoria técnica atual](DOCUMENTACAO_COMPLETA.md#doc-docs-14-auditoria-readme-md) e o [guia de manutenção](DOCUMENTACAO_COMPLETA.md#doc-docs-14-auditoria-guia-manutencao-md). Confira branch e alterações locais antes de editar; preserve trabalho preexistente.
- O servidor é Flask/Python em `app/`; o cliente C#/WPF em `desktop_wpf/` consome `/api/v1`. Não tratar WPF como backend nem presumir SPA React.
- Vendas, estoque e caixa têm serviços em `app/services/`. Web e API ainda duplicam parsers e relatórios; verificar ambos antes de alterar regras. Divergências financeiras conhecidas constam em [riscos conhecidos](DOCUMENTACAO_COMPLETA.md#doc-docs-14-auditoria-riscos-md).
- Identidade usa banco central; operações usam sessão tenant e escopo de empresa. Obtenha empresa da autenticação, nunca de campo livre enviado pelo cliente. Preserve Decimal/Numeric e helpers de `app/money.py` e `app/time_utils.py`.
- Mudança de entidade requer revisão das árvores Alembic central/tenant e testes de upgrade. Não executar a factory, scripts de migration/cleanup ou `tenants-status` contra banco real como se fossem leitura sem efeitos.
- Testes Python usam `unittest`; configure `APP_BASE_DIR` temporário, `TESTING=1`, `MAIL_SUPPRESS_SEND=1`, `APP_ENV=development` e `PYTHONDONTWRITEBYTECODE=1` antes de importar. A suíte usa SQLite; ela não comprova locks/isolamento físico MySQL.
- Testes WPF estão em `desktop_wpf/tests/Girofy.UnitTests` e exigem ambiente Windows adequado. Preserve compatibilidade dos DTOs, protocolo e armazenamento Girofy; não renomeie automaticamente esses identificadores.
- Não incluir `.env`, dumps, bases locais, tokens, dados pessoais ou logs reais em documentação/testes. Atualize módulo, API, regras e dicionário quando contratos mudarem.
- Em tarefas explicitamente restritas a auditoria sem deploy, registre publicação e teste manual HML como pendentes; não flexibilize a regra de autorização de produção acima.

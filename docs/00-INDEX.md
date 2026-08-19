# Índice da documentação Girofy

Este índice é o ponto inicial oficial. A documentação separa interface Web, aplicativo Windows e regras compartilhadas no servidor.

## Marco atual

- [Documentação consolidada atual](../documentacao/DOCUMENTACAO_COMPLETA.txt) —
  fonte completa atualizada em 19/08/2026, separando Web, App, API e infraestrutura.
- [Estado completo em 17/08/2026](31-estado-atual-17-08-2026.md) — marco histórico detalhado.
- [Marco de 13/08/2026](30-versao-atual-13-08-2026.md) — histórico preservado.

## Visão consolidada

- [Matriz resumida de plataformas](MATRIX.md)
- [Paridade funcional detalhada](FEATURE_PARITY.md)
- [Fluxos de build e publicação](WORKFLOWS.md)
- [Instalador Windows 0.8.0](WINDOWS_INSTALLER.md)
- [Estado Web e Windows](24-estado-versoes-web-windows.md)
- [Arquitetura](03-arquitetura.md)
- [Regras de negócio](05-regras-negocio.md)
- [API](09-api.md)
- [Permissões](11-permissoes.md)
- [Testes](15-testes.md)
- [Segurança](14-seguranca.md)
- [Migrations central/tenant](29-migracoes-versionadas.md)
- [Rate limit Redis](28-rate-limit-redis.md)
- [Cancelamento de vendas](27-cancelamento-estorno-vendas.md)
- [Notificações e e-mail](25-notificacoes-web-windows-email.md)

## Documentação por plataforma

- [Web](web/README.md): telas Flask/Jinja, sessão no navegador e painel master.
- [App Windows](app/README.md): cliente WPF, cache de sessão e consumo da API.
- [Compartilhado](shared/README.md): API, serviços transacionais, banco, tenant, auditoria e erros.
- [Temas claro e escuro](shared/THEMING.md): tokens, persistência, toggle e validação Web/App.

Os documentos numerados continuam contendo os manuais temáticos e históricos. Em caso de conflito, a matriz de paridade e os documentos por plataforma descrevem o estado atual do código.

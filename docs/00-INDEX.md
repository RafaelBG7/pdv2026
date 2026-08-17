# Índice da documentação Girofy

Este índice é o ponto inicial oficial. A documentação separa interface Web, aplicativo Windows e regras compartilhadas no servidor.

## Visão consolidada

- [Matriz resumida de plataformas](MATRIX.md)
- [Paridade funcional detalhada](FEATURE_PARITY.md)
- [Fluxos de build e publicação](WORKFLOWS.md)
- [Estado Web e Windows](24-estado-versoes-web-windows.md)
- [Arquitetura](03-arquitetura.md)
- [Regras de negócio](05-regras-negocio.md)
- [API](09-api.md)
- [Permissões](11-permissoes.md)
- [Testes](15-testes.md)

## Documentação por plataforma

- [Web](web/README.md): telas Flask/Jinja, sessão no navegador e painel master.
- [App Windows](app/README.md): cliente WPF, cache de sessão e consumo da API.
- [Compartilhado](shared/README.md): API, serviços transacionais, banco, tenant, auditoria e erros.

Os documentos numerados continuam contendo os manuais temáticos e históricos. Em caso de conflito, a matriz de paridade e os documentos por plataforma descrevem o estado atual do código.

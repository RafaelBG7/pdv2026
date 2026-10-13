# Segurança: entrega em homologação

Este lote remove bancos e dumps do índice Git, impede seu retorno pela CI,
revoga sessões web/remember após troca de senha e exige cookies Secure em ambientes protegidos.
Sessões antigas sem vínculo com a credencial serão encerradas no primeiro acesso após deploy.

Os workflows de produção preparados neste lote deixam de publicar automaticamente por push,
restringem deploy a main e conferem que a árvore é idêntica ao SHA com deploy HML aprovado na CI.
Essa verificação automatizada NÃO comprova teste manual nem autorização do usuário.

## Pendências antes de considerar a contenção concluída

- O usuário pediu para manter o repositório público em 13/10/2026.
- A remoção no novo commit não remove arquivos de main, histórico, forks e clones.
- A limpeza de histórico exige operação coordenada, inventário das referências e autorização específica.
- Identificar titulares/origem dos registros expostos e rotacionar credenciais afetadas;
  não reaproveitar senhas publicadas nem registrar hashes/senhas em evidências.
- Após teste manual HML e autorização explícita, aplicar proteção de main e do ambiente production,
  restringir deployments a main e exigir aprovação do proprietário sem bypass administrativo.
- Promover somente o conteúdo validado e gerar a versão após autorização.

## Teste manual HML

Conferir login HTTPS, cookies Secure/HttpOnly/SameSite e HSTS.
Com conta descartável, abrir duas sessões, habilitando lembrar em uma delas;
alterar a senha e verificar que ambas deixam de acessar conteúdo protegido,
inclusive após remover o cookie de sessão mantendo apenas o remember.
Validar novo login e logout. Não usar contas nem alterar credenciais de produção.

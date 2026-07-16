# Análise da Migração Windows Nativa

## Objetivo

O Girofy web continua sendo o produto estável e permanece publicado na OCI em:

```text
http://168.75.101.126:18080
```

A eventual versão Windows é desenvolvida separadamente em `desktop_wpf/`. Ela usa
C#, .NET 8, WPF e MVVM, com telas realmente nativas e integração exclusivamente pela
API REST do Flask. Nenhuma etapa dessa migração substitui ou interrompe a versão web.

## Estado Atual

Já existem no cliente WPF:

- solução separada em camadas Application, Infrastructure, Desktop e UnitTests;
- configuração segura do endereço da API;
- verificação de conectividade em `GET /api/v1/health`;
- login por usuário ou e-mail;
- access token curto e refresh token rotativo;
- sessão local protegida pelo DPAPI do Windows;
- restauração de sessão, logout e revogação de token;
- opção de lembrar apenas o identificador do usuário;
- shell autenticado com navegação entre Produtos e Categorias;
- API de catálogo paginada, filtrada pela empresa do token;
- busca, filtros, ordenação e tabelas WPF virtualizadas;
- logs locais rotativos sem senha ou token completo;
- workflow Windows para testes e build de prévia.

O backend mantém autenticação, tenant, assinatura, permissões e regras de negócio como
fonte de verdade. O cliente nunca acessa o MySQL diretamente.

## Princípios da Migração

1. Preservar integralmente o Flask/Jinja e o deploy OCI.
2. Criar endpoints versionados em `/api/v1` sem duplicar regras de negócio.
3. Exigir HTTPS para credenciais e tokens fora de desenvolvimento controlado.
4. Migrar um módulo de cada vez, começando por consultas somente leitura.
5. Aplicar paginação, cancelamento e virtualização para manter baixo consumo.
6. Tratar vendas e caixa com idempotência e validação transacional no servidor.
7. Manter testes de contrato entre API e cliente nativo.

## Ordem Recomendada

1. Publicar a OCI atrás de domínio e HTTPS.
2. Adicionar cache local limitado por tenant para consultas não sensíveis.
3. Implementar detalhes e edição de produtos conforme as permissões.
4. Migrar estoque com trilha de auditoria e controle de concorrência.
5. Migrar caixa e vendas com chaves de idempotência.
6. Preparar assinatura digital, instalador e atualização apenas quando o cliente nativo
   alcançar paridade suficiente com o fluxo web.

## Critério de Liberação

O WPF só deve ser distribuído para clientes quando os módulos necessários estiverem
completos, os endpoints estiverem protegidos por HTTPS, os testes Windows passarem e a
versão web continuar disponível como contingência.

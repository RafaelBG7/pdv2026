# Arquitetura do Girofy para Windows

## Coexistência

Durante a migração existem dois canais independentes:

```text
Navegador --------> Flask/Jinja -----------+--> Services --> MySQL atual
WPF nativo -------> API Flask /api/v1 -----+
```

Nenhum cliente desktop possui credenciais do MySQL. O tenant é sempre determinado no servidor a partir da identidade autenticada.

## Estrutura do WPF

- `Girofy.Application`: contratos da aplicação, modelos da API, MVVM e ViewModels sem acesso a infraestrutura.
- `Girofy.Infrastructure`: cliente HTTP, configuração, abertura segura do navegador e logs locais.
- `Girofy.Desktop`: composição WPF, recursos visuais e janelas.
- `Girofy.UnitTests`: testes de comportamento que não dependem da interface gráfica.

A camada `Domain` ainda não foi criada porque não existe lógica de domínio nativa no cliente. Regras críticas continuam no Flask e serão representadas no desktop apenas quando houver necessidade real.

## Segurança da conexão

O health check pode operar por HTTP durante a transição, mas os endpoints de autenticação
exigem HTTPS. O backend retorna HTTP `426` antes de ler credenciais quando a conexão não
é segura. Atrás de proxy reverso confiável, `TRUST_PROXY_HEADERS=1` permite reconhecer
`X-Forwarded-Proto: https`.

Fluxo de autenticação nativo:

```text
Login WPF -> POST /api/v1/auth/login -> access token + refresh token
   |                                           |
   |                                           +-> hash no MySQL central
   +-> DPAPI CurrentUser em %LOCALAPPDATA%\Girofy\auth.dat

Inicialização -> refresh rotativo -> sessão anterior revogada -> novo par protegido
Logout -> revogação no servidor + remoção local obrigatória
```

O cliente não salva senha. A opção “Lembrar usuário” persiste apenas o identificador em
JSON. Alteração de senha, usuário/empresa inativos ou assinatura vencida são revalidados
no servidor e bloqueiam a sessão.

Configurações reconhecidas:

- `GIROFY_API_BASE_URL`
- `GIROFY_ALLOW_INSECURE_HTTP`
- `GIROFY_API_TIMEOUT_SECONDS`

Configurações do servidor:

- `API_TOKEN_SECRET`
- `API_ACCESS_TOKEN_MINUTES`
- `API_REFRESH_TOKEN_DAYS`
- `API_LOGIN_ATTEMPT_LIMIT`
- `API_LOGIN_BLOCK_SECONDS`
- `API_ALLOW_INSECURE_AUTH`
- `TRUST_PROXY_HEADERS`

## Próximas etapas

1. Publicar o backend atrás de domínio e HTTPS.
2. Adicionar cache de leitura limitado e invalidação por tenant.
3. Implementar detalhes e edição de produtos conforme as permissões.
4. Migrar movimentações de estoque com controle de concorrência.
5. Migrar vendas e caixa somente após contratos de idempotência e concorrência.

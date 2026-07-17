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
2. Implementar detalhes e edição de produtos conforme as permissões.
3. Migrar movimentações de estoque com controle de concorrência.
4. Migrar relatórios e módulos administrativos por consultas agregadas.

## Dashboard nativo

O cliente consulta `GET /api/v1/dashboard/summary` após autenticação. O endpoint agrega os
dados no servidor e devolve apenas a adega vinculada ao token. Nenhum `company_id` enviado
na query altera o tenant.

O contrato inclui vendas de hoje, caixa atual, formas de pagamento, produtos mais vendidos,
estoque baixo, vendas recentes e contas críticas. Lucro, ticket médio, totais do caixa,
pagamentos e contas são omitidos quando as permissões do usuário não autorizam a leitura.
Produtos e categorias são carregados somente ao abrir o respectivo módulo.

## Caixa nativo

O módulo Caixa consome `GET /api/v1/cash-registers/summary` somente quando o usuário abre
a tela. Abertura e fechamento usam endpoints transacionais próprios; o servidor serializa
as operações no escopo da empresa, confere o valor esperado e registra auditoria. O cliente
preserva o valor digitado quando a conferência falha e nunca acessa o MySQL diretamente.

Usuários com `can_manage_cash_register` podem operar o módulo. Valores iniciais, totais,
diferenças e formas de pagamento só são enviados quando a identidade também possui
`can_view_reports`.

## Venda nativa

O módulo Vendas pesquisa o catálogo existente, mantém o pedido em memória no WPF e envia
somente a confirmação final para `POST /api/v1/sales`. O endpoint exige caixa aberto e
executa venda, itens, pagamentos, estoque e auditoria na mesma transação do banco da adega.

Cada rascunho recebe uma chave de idempotência. Se houver timeout depois de o servidor
confirmar a transação, o cliente reutiliza a mesma chave e recupera o comprovante, sem
duplicar venda ou movimentação de estoque. Um erro validável preserva produtos, desconto
e pagamentos para correção e nova tentativa.

As regras de produto ativo, kit, estoque negativo, desconto, taxas de Pix/débito/crédito,
pagamento mínimo e permissão continuam centralizadas no Flask. O WPF calcula uma prévia
para agilizar a operação, mas a resposta do servidor é sempre a fonte de verdade.

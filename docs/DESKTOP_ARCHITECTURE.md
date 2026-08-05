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

Assinatura vencida -> POST /api/v1/subscription/activate -> key aplicada à adega
                 +-> nova sessão emitida somente após senha + key válidas

Inicialização -> refresh rotativo -> sessão anterior revogada -> novo par protegido
Logout -> revogação no servidor + remoção local obrigatória
```

Fluxos públicos no login:

- `Criar uma conta` monta `/login?auth_tab=register` a partir da mesma URL base
  configurada para o servidor e abre o cadastro web no navegador padrão.
- `Esqueci minha senha` abre um diálogo WPF que envia somente usuário ou e-mail para
  `POST /api/v1/auth/password-recovery/request`.
- o servidor devolve a mesma confirmação pública independentemente de a conta existir;
  quando aplicável, reutiliza o serviço de recuperação web e envia o link por e-mail.
- o token e a definição da nova senha permanecem exclusivamente em
  `/reset-password/<token>` no navegador. O cliente Windows não recebe nem processa o
  token.

O cliente não salva senha. A opção “Lembrar usuário” persiste apenas o identificador em
JSON. Alteração de senha, usuário/empresa inativos ou assinatura vencida são revalidados
no servidor e bloqueiam a sessão. Quando a assinatura estiver vencida, o login normal
retorna `subscription_required` e o WPF mostra a tela de ativação. A ativação usa usuário,
senha e key; o servidor aplica a key apenas na própria adega do usuário autenticado e já
retorna um novo par de tokens.

Configurações reconhecidas:

- `GIROFY_API_BASE_URL`
- `GIROFY_ALLOW_INSECURE_HTTP`
- `GIROFY_API_TIMEOUT_SECONDS`

A URL web desses fluxos usa a própria `Api.BaseUrl`/`GIROFY_API_BASE_URL`, pois API e
site são publicados no mesmo servidor. Não há domínio ou rota codificados nos ViewModels.

Para validar localmente, execute os testes Python de rotas, `dotnet test` na solução e
abra o login no Windows. Confirme o cadastro no navegador, o diálogo de recuperação, o
estado de envio e a mensagem genérica. O recebimento real exige SMTP configurado.

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
2. Ampliar detalhes e manutenção avançada de catálogo conforme as permissões.
3. Aprofundar relatórios com detalhamento por produto, caixa e comparativos avançados.
4. Migrar fluxos administrativos avançados restantes, como ajustes de plano.

## Dashboard nativo

O cliente consulta `GET /api/v1/dashboard/summary` após autenticação. O endpoint agrega os
dados no servidor e devolve apenas a adega vinculada ao token. Nenhum `company_id` enviado
na query altera o tenant.

O contrato inclui vendas de hoje, caixa atual, formas de pagamento, produtos mais vendidos,
estoque baixo, vendas recentes e contas críticas. Lucro, ticket médio, totais do caixa,
pagamentos e contas são omitidos quando as permissões do usuário não autorizam a leitura.
Produtos e categorias são carregados somente ao abrir o respectivo módulo.

## Instância única e reentrância

O processo WPF adquire `Local\Girofy.Desktop.SingleInstance` antes de construir o host.
Uma segunda inicialização na mesma sessão encerra imediatamente, evitando múltiplos hosts,
clientes HTTP e janelas quando o usuário clica repetidamente no executável.

Comandos assíncronos bloqueiam reentrância para operações comuns. Consultas substituíveis,
como o detalhe de caixas anteriores, cancelam a chamada anterior e aplicam somente a versão
mais recente compatível com seleção e sessão. O roteiro de estresse e os critérios para
retomar funcionalidades estão em `docs/26-desempenho-estabilidade-windows.md`.

A navegação principal possui um `CancellationTokenSource` compartilhado no
`ConnectionViewModel`. Trocar de módulo cancela a inicialização anterior, impedindo que
cliques rápidos disparem cargas simultâneas de Dashboard, Catálogo, Caixa e outros módulos.

## Caixa nativo

O módulo Caixa consome `GET /api/v1/cash-registers/summary` somente quando o usuário abre
a tela. Abertura e fechamento usam endpoints transacionais próprios; o servidor serializa
as operações no escopo da empresa, confere o valor esperado e registra auditoria. O cliente
preserva o valor digitado quando a conferência falha e nunca acessa o MySQL diretamente.

Usuários com `can_manage_cash_register` podem operar o módulo. Valores iniciais, totais,
diferenças e formas de pagamento só são enviados quando a identidade também possui
`can_view_reports`.

A interface separa o fluxo em uma navegação secundária entre `Caixa atual` e
`Caixas anteriores`. O resumo dos dez caixas encerrados é carregado com o snapshot, mas
vendas, itens e pagamentos são obtidos apenas ao selecionar um registro. A grade utiliza
virtualização e reciclagem de linhas; cada venda do detalhe usa um `Expander`, reduzindo o
custo visual do histórico. Depois de um fechamento bem-sucedido, a interface seleciona
automaticamente `Caixas anteriores`.

O estado das opções fica no `CashRegisterViewModel`; o code-behind apenas encaminha a
seleção da grade ao comando assíncrono. Estados vazio, carregando, com detalhe e sem vendas
são controlados por bindings. Consulte `docs/25-caixas-windows.md` para o contrato completo
de UX, segurança, testes e critérios de aceite.

## Catálogo de produtos expansível

A listagem de Produtos reutiliza o objeto `CatalogProduct` recebido na consulta paginada.
Selecionar uma linha abre um `RowDetailsTemplate` com os dados completos já disponíveis,
sem endpoint adicional e sem duplicar estado no `CatalogViewModel`. A grade mantém
virtualização de linhas e colunas com reciclagem de contêineres.

Propriedades de apresentação no modelo formatam moeda em `pt-BR`, estoque, tipo, situação
e valores opcionais. Custo e lucro permanecem nulos quando o backend os omite por falta de
permissão e são exibidos como `Não disponível`. A expansão é somente leitura; edição
continua sendo uma ação explícita e protegida por `can_manage_products`.

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

O módulo também consulta `GET /api/v1/sales/today` para o histórico disponível e
`GET /api/v1/sales/{id}` para detalhes. A interface permite atualização manual, expande
itens e pagamentos e reutiliza o mesmo comprovante nativo da venda recém-concluída, sem
registrar ou alterar dados. Não existe infraestrutura de impressão no cliente atual.

O contrato de listagem existente é limitado ao dia atual ou ao caixa aberto e não oferece
parâmetros de filtro, paginação nem total de registros. Por isso o Windows não simula
filtros ou páginas sobre uma lista baixada integralmente. Período, número, operador, forma
de pagamento e paginação permanecem indisponíveis até que o backend forneça um contrato
de consulta apropriado. Cancelamento, estorno e edição continuam fora do escopo.

## Estoque nativo

O módulo Estoque consome `GET /api/v1/stock/movements`, `POST /api/v1/stock/entries` e
`POST /api/v1/stock/adjustments`. O cliente exibe histórico paginado, filtros, resumo de
entradas/saídas e formulários de entrada e ajuste manual, mas a alteração real do saldo é
sempre executada no backend.

O Flask usa o `stock_service` para aplicar bloqueios por empresa/produto, validar estoque
negativo conforme a configuração da adega, gravar `stock_movements` e registrar auditoria.
Usuários sem `can_view_stock_movements` não acessam o histórico; usuários sem
`can_manage_stock` visualizam o histórico autorizado, mas não conseguem enviar entrada ou
ajuste.

## Relatórios nativos

O módulo Relatórios consome `GET /api/v1/reports/summary` e
`GET /api/v1/reports/products`. A consulta aceita períodos diário, semanal, mensal, anual
e personalizado, além da alternância do gráfico entre faturamento e quantidade de vendas.

O backend calcula os cartões principais, totais por forma de pagamento, ranking de
produtos, buckets do gráfico e performance paginada por produto dentro do banco da adega
autenticada. O WPF não recebe listas completas de vendas para recalcular localmente, o que
mantém a tela mais leve em máquinas simples e reduz tráfego.

O relatório por produto traz quantidade vendida, faturamento, custo, lucro, ticket médio e
estoque atual, com busca e ordenação feitas por endpoint para evitar processamento pesado
no cliente Windows.

O acesso depende de `can_view_reports`. Usuários sem essa permissão continuam autenticados,
mas a navegação de relatórios fica indisponível no cliente e o servidor retorna
`permission_denied` se o endpoint for chamado diretamente.

## Configurações e importação

O módulo Configurações consome endpoints versionados para perfil, senha, backup,
exportação, importação e gestão básica de equipe. A importação de produtos usa
`POST /api/v1/settings/import/products` com `multipart/form-data` e arquivo `.csv` ou
`.xlsx` escolhido pela janela nativa do Windows.

O backend interpreta os cabeçalhos conhecidos, cria categorias ausentes dentro da própria
adega, cria ou atualiza produtos por código de barras ou nome, ajusta o estoque quando a
planilha informa quantidade e registra movimentação e auditoria. O cliente Windows não
processa regra de negócio nem acessa o MySQL: ele apenas seleciona o arquivo, envia os
bytes para a API e mostra o resumo de criados, atualizados, ignorados e movimentações.

Usuários `admin`, `manager` e `master` podem importar. Funcionários comuns recebem
`permission_denied`, mesmo que tentem chamar o endpoint diretamente.

# Girofy para Windows - WPF

Esta pasta contém a aplicação Windows nativa experimental do Girofy. Ela é independente da interface Flask/Jinja e não acessa o MySQL diretamente.

## Estado atual

Décimo sétimo corte vertical implementado:

- solução C# em .NET 8 LTS;
- telas nativas em WPF;
- MVVM sem dependência de framework visual externo;
- injeção de dependência e `HttpClientFactory`;
- consulta real a `GET /api/v1/health`;
- login nativo por usuário ou e-mail em `POST /api/v1/auth/login`;
- ativação nativa de assinatura vencida por key em `POST /api/v1/subscription/activate`;
- renovação automática da sessão por refresh token rotativo;
- consulta da identidade autenticada e logout revogável;
- bloqueios de usuário e adega aplicados no servidor, com regularização de assinatura
  diretamente no cliente Windows quando uma key válida é informada;
- opção `Lembrar usuário`, sem armazenar a senha;
- sessão criptografada com DPAPI para o usuário atual do Windows;
- timeout e cancelamento;
- tela de disponibilidade do servidor;
- shell autenticado com navegação lateral nativa;
- dashboard nativo com caixa atual, vendas de hoje, ticket médio, lucro conforme
  permissão, formas de pagamento, estoque baixo e vendas recentes;
- carregamento agregado em `GET /api/v1/dashboard/summary`, sempre restrito à adega
  presente no token;
- ocultação de lucro, totais do caixa, formas de pagamento e contas a pagar quando o
  perfil não possui as permissões correspondentes;
- consulta paginada de produtos por nome ou código de barras;
- filtro por categoria e status, com ordenação por nome, preço ou estoque;
- consulta de categorias com quantidade de produtos;
- cadastro, edição e exclusão nativos de categorias para usuários com
  `can_manage_categories`;
- categorias integradas aos endpoints `POST`, `PUT` e `DELETE /api/v1/catalog/categories`;
- exclusão protegida contra categorias com produtos vinculados;
- tabelas WPF virtualizadas para reduzir consumo com catálogos grandes;
- custo e lucro omitidos pelo servidor quando o perfil não pode gerenciar produtos;
- cadastro e edição nativos de produtos para usuários com `can_manage_products`;
- formulário de produto com nome, código de barras, categoria, custo, venda, estoque,
  estoque mínimo e status;
- criação e edição integradas aos endpoints `POST /api/v1/catalog/products` e
  `PUT /api/v1/catalog/products/{id}`;
- ajustes de estoque feitos no servidor com trava, movimentação e auditoria;
- validação por adega para categoria, código de barras duplicado e permissões;
- tela nativa de Caixa com consulta do caixa atual e dos dez caixas fechados mais
  recentes;
- detalhe nativo de caixa selecionado em `GET /api/v1/cash-registers/{id}`, com linha
  do tempo cronológica das vendas, itens vendidos e pagamentos;
- abertura de caixa com valor inicial e proteção contra dois caixas simultâneos;
- fechamento com conferência exata do valor esperado, sem perder o valor digitado em
  caso de divergência;
- totais por forma de pagamento e valores do caixa exibidos apenas para usuários com
  permissão de relatórios;
- abertura e fechamento registrados na auditoria da adega;
- tela nativa de Vendas com busca por nome ou código de barras em ordem alfabética;
- carrinho com múltiplos produtos, quantidades ajustáveis, desconto em reais e remoção
  de itens;
- pagamentos combinados em Dinheiro, Pix, Débito e Crédito, com preenchimento do valor
  restante, cálculo de falta e troco;
- registro transacional em `POST /api/v1/sales`, com caixa obrigatório, baixa de estoque,
  kits, taxas da maquininha, auditoria e isolamento pela adega do token;
- chave de idempotência preservada nas tentativas para impedir vendas duplicadas quando
  a conexão falha depois da gravação;
- pedido preservado no cliente quando o servidor rejeita ou não confirma a venda;
- comprovante nativo após a conclusão e início imediato de uma nova venda;
- tela nativa de Estoque com histórico paginado de movimentações;
- filtros de estoque por busca, categoria, tipo de movimentação e origem;
- resumo de entradas, saídas, total de movimentações e produtos movimentados;
- entrada manual de mercadoria integrada a `POST /api/v1/stock/entries`;
- ajuste manual de estoque integrado a `POST /api/v1/stock/adjustments`;
- histórico integrado a `GET /api/v1/stock/movements`, sempre limitado à adega do token;
- permissões `can_view_stock_movements` e `can_manage_stock` respeitadas no cliente e
  no servidor;
- tela nativa de Relatórios com período diário, semanal, mensal, anual e personalizado;
- alternância do gráfico entre faturamento e quantidade de vendas;
- cards de vendas, itens, subtotal, desconto, total final, lucro e ticket médio;
- totais por forma de pagamento e ranking dos dez produtos mais vendidos;
- relatório integrado a `GET /api/v1/reports/summary`, com agregação no backend e
  isolamento pela adega do token;
- relatório por produto integrado a `GET /api/v1/reports/products`;
- consulta paginada de performance por produto com quantidade vendida, faturamento,
  custo, lucro, ticket médio e estoque atual;
- filtros do relatório por produto por busca e ordenação por mais vendidos, maior
  faturamento, maior lucro, menor estoque ou produtos sem venda;
- acesso ao relatório bloqueado para perfis sem `can_view_reports`;
- tela nativa de Contas a pagar com resumo de abertas, vencidas, próximas e pagas;
- filtros por busca, status, categoria e período de vencimento;
- cadastro de contas com descrição, categoria, valor, vencimento e observações;
- marcação de conta como paga e reabertura de conta paga;
- integração com `GET /api/v1/payables`, `POST /api/v1/payables`,
  `POST /api/v1/payables/{id}/pay` e `POST /api/v1/payables/{id}/reopen`;
- acesso ao módulo de contas bloqueado para perfis sem `can_manage_payables`;
- tela nativa de Auditoria com consulta paginada de eventos críticos;
- filtros de auditoria por busca, usuário, ação, módulo, método e período;
- resumo de eventos, usuários envolvidos e ações diferentes;
- detalhes expansíveis com valores antes/depois, rota, método, request id e IP;
- integração com `GET /api/v1/audit/logs`, sempre restrita à adega presente no token;
- acesso à auditoria bloqueado para perfis sem `can_view_audit_logs`;
- tela nativa de Configurações com resumo da conta, adega, assinatura e regras da empresa;
- edição nativa de nome, sobrenome e telefone em `PUT /api/v1/settings/profile`;
- troca de senha nativa em `PUT /api/v1/settings/password`, com revogação das sessões do
  usuário e retorno automático para login;
- edição nativa das regras da adega em `PUT /api/v1/settings/company`, incluindo venda
  com estoque negativo e taxas de Pix, débito e crédito usadas no lucro;
- configuração nativa de frequência de backup em `PUT /api/v1/settings/backup`;
- geração de backup manual em `POST /api/v1/settings/backup/run`, reutilizando o mesmo
  motor de backup da versão web;
- exportação nativa em CSV para administradores em `GET /api/v1/settings/export/{tipo}`;
- tipos de exportação disponíveis no cliente Windows: produtos, vendas, caixas e contas a
  pagar;
- o arquivo exportado é salvo pelo usuário com a janela nativa do Windows, sem guardar dados
  sensíveis no cliente;
- importação nativa de produtos por CSV/XLSX em `POST /api/v1/settings/import/products`;
- a importação cria categorias quando necessário, cria ou atualiza produtos, ajusta estoque
  e registra auditoria sempre dentro da adega autenticada;
- gestão nativa de equipe para administradores, gerentes e usuários com permissão de
  configurações;
- busca de funcionários por nome, usuário ou CPF em `GET /api/v1/settings/team`;
- cadastro nativo de funcionário comum, gerente ou admin em `POST /api/v1/settings/team`;
- edição nativa de nome, sobrenome, CPF, e-mail, telefone, perfil e status em
  `PUT /api/v1/settings/team/{id}`;
- regras de equipe aplicadas no servidor: isolamento por adega, CPF único dentro da adega,
  username global único, perfis padronizados e proteção contra autodesativação;
- resumo e edição das taxas de Pix, débito e crédito e da regra de venda sem estoque;
- integração com `GET /api/v1/settings/account`, sempre restrita ao usuário autenticado e
  à adega presente no token;
- abertura opcional da versão web no navegador externo;
- logs locais em `%LOCALAPPDATA%\Girofy\logs`;
- catálogo carregado somente quando Produtos ou Categorias é aberto, evitando consultas
  e uso de memória desnecessários na inicialização;
- testes unitários de conexão, login, restauração de sessão, logout, dashboard, catálogo,
  caixa, vendas, estoque, relatórios, contas a pagar e exportação de configurações;
- workflow separado para build Windows self-contained.

O dashboard, o catálogo, a manutenção básica de produtos e categorias, o caixa, o registro
de vendas, o estoque operacional, os relatórios resumidos e por produto, contas a pagar,
auditoria, configurações pessoais, regras operacionais da adega, taxas de maquininha,
backup manual/frequência, importação de produtos, exportação CSV, gestão básica de equipe
e ativação por key já funcionam de forma nativa.
As demais configurações administrativas avançadas continuam disponíveis pela versão web
enquanto são migradas por etapas, sem remover nem substituir a versão web durante a
transição.

## Configuração

O arquivo `src/Girofy.Desktop/appsettings.json` contém a URL padrão da API. Ela pode ser substituída no Windows sem recompilar:

```powershell
$env:GIROFY_API_BASE_URL = "https://seu-dominio"
$env:GIROFY_ALLOW_INSECURE_HTTP = "false"
```

O endereço OCI atual ainda usa HTTP e pode ser usado somente no health check. Login e
tokens são recusados pelo backend com HTTP `426` enquanto não houver HTTPS. Para um teste
temporário em rede controlada é possível definir `API_ALLOW_INSECURE_AUTH=1` no servidor,
mas isso transmite senha e token sem criptografia e não deve ser distribuído a clientes.

As informações locais ficam em:

```text
%LOCALAPPDATA%\Girofy\auth.dat          sessão criptografada com DPAPI
%LOCALAPPDATA%\Girofy\preferences.json somente usuário lembrado
%LOCALAPPDATA%\Girofy\logs              logs técnicos sem senha/token
```

## Desenvolvimento no Windows

Requisitos para desenvolvedores:

- Windows 10 ou 11;
- .NET 8 SDK;
- Visual Studio 2022 opcional.

Comandos:

```powershell
dotnet restore .\desktop_wpf\Girofy.Desktop.sln
dotnet test .\desktop_wpf\Girofy.Desktop.sln
dotnet run --project .\desktop_wpf\src\Girofy.Desktop\Girofy.Desktop.csproj
```

## Build pelo GitHub

Execute manualmente:

```text
GitHub > Actions > Build Windows WPF preview > Run workflow
```

O artefato `Girofy-Windows-WPF-preview` é self-contained. O cliente final não precisa instalar .NET, Python, MySQL ou ferramentas de desenvolvimento.

Esta prévia valida a base nativa, o ciclo completo de autenticação, o dashboard operacional,
a consulta e manutenção básica do catálogo, o fluxo de abertura/fechamento de caixa, o
registro completo de vendas, o estoque operacional, os relatórios resumidos e por produto,
contas a pagar, auditoria, configurações pessoais, backup, importação de produtos,
exportação CSV, gestão básica de equipe e ativação por key de assinatura. Ela ainda não substitui a versão web em produção porque as
configurações administrativas avançadas restantes e o HTTPS público ainda não atingiram o
critério de liberação.

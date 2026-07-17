# Girofy para Windows - WPF

Esta pasta contém a aplicação Windows nativa experimental do Girofy. Ela é independente da interface Flask/Jinja e não acessa o MySQL diretamente.

## Estado atual

Quinto corte vertical implementado:

- solução C# em .NET 8 LTS;
- telas nativas em WPF;
- MVVM sem dependência de framework visual externo;
- injeção de dependência e `HttpClientFactory`;
- consulta real a `GET /api/v1/health`;
- login nativo por usuário ou e-mail em `POST /api/v1/auth/login`;
- renovação automática da sessão por refresh token rotativo;
- consulta da identidade autenticada e logout revogável;
- bloqueios de usuário, adega e assinatura aplicados no servidor;
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
- tabelas WPF virtualizadas para reduzir consumo com catálogos grandes;
- custo e lucro omitidos pelo servidor quando o perfil não pode gerenciar produtos;
- tela nativa de Caixa com consulta do caixa atual e dos dez caixas fechados mais
  recentes;
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
- abertura opcional da versão web no navegador externo;
- logs locais em `%LOCALAPPDATA%\Girofy\logs`;
- catálogo carregado somente quando Produtos ou Categorias é aberto, evitando consultas
  e uso de memória desnecessários na inicialização;
- testes unitários de conexão, login, restauração de sessão, logout, dashboard, catálogo,
  caixa e vendas;
- workflow separado para build Windows self-contained.

O dashboard, o catálogo, o caixa e o registro de vendas já funcionam de forma nativa.
Ainda não existem edição de produtos, movimentação manual de estoque, relatórios completos,
contas a pagar, auditoria e configurações no WPF. Esses módulos serão adicionados por API
sem remover nem substituir a versão web durante a migração.

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
a consulta real do catálogo, o fluxo de abertura/fechamento de caixa e o registro completo
de vendas. Ela ainda não substitui a versão web em produção porque os módulos administrativos
e o HTTPS público ainda não atingiram o critério de liberação.

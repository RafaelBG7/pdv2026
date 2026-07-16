# Girofy para Windows - WPF

Esta pasta contém a aplicação Windows nativa experimental do Girofy. Ela é independente da interface Flask/Jinja e não acessa o MySQL diretamente.

## Estado atual

Terceiro corte vertical implementado:

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
- consulta paginada de produtos por nome ou código de barras;
- filtro por categoria e status, com ordenação por nome, preço ou estoque;
- consulta de categorias com quantidade de produtos;
- tabelas WPF virtualizadas para reduzir consumo com catálogos grandes;
- custo e lucro omitidos pelo servidor quando o perfil não pode gerenciar produtos;
- abertura opcional da versão web no navegador externo;
- logs locais em `%LOCALAPPDATA%\Girofy\logs`;
- testes unitários de conexão, login, restauração de sessão, logout e catálogo;
- workflow separado para build Windows self-contained.

O catálogo já funciona em modo somente leitura. Ainda não existem edição de produtos,
vendas, estoque operacional ou caixa nativos no WPF. Esses módulos serão adicionados por
API sem remover nem substituir a versão web durante a migração.

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

Esta prévia valida a base nativa, o ciclo completo de autenticação e a consulta real do
catálogo. Ela ainda não substitui a versão web em produção porque vendas e caixa não
foram migrados.

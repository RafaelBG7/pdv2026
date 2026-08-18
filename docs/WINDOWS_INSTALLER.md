# Instalador do GiroFy Windows 0.8.0

## Visão geral

O GiroFy Windows 0.8.0 é a primeira entrega com instalador reproduzível. Trata-se de uma versão de desenvolvimento/preview, não da distribuição comercial 1.0.0.

O fluxo preserva o publish existente:

```text
dotnet publish self-contained/single-file
    → Girofy.exe e arquivos de configuração
    → Inno Setup
    → GiroFy-Setup-0.8.0.exe
```

O instalador não altera a arquitetura do produto: o App continua sendo WPF/.NET 8, usa `/api/v1`, não acessa MySQL, não executa migrations e não possui banco operacional local.

## Auditoria do projeto

| Item | Estado confirmado no código |
|---|---|
| Solução | `desktop_wpf/Girofy.Desktop.sln` |
| Executável | `desktop_wpf/src/Girofy.Desktop/Girofy.Desktop.csproj` |
| Application | `desktop_wpf/src/Girofy.Application` |
| Infrastructure | `desktop_wpf/src/Girofy.Infrastructure` |
| Testes | `desktop_wpf/tests/Girofy.UnitTests` |
| Framework | `net8.0-windows` |
| Runtime | `win-x64` |
| Assembly | `Girofy`, produzindo `Girofy.exe` |
| Publish | self-contained, single-file, nativas incluídas e compressão habilitada |
| Trimming | não habilitado |
| Configuração API | `appsettings.json`, variáveis `GIROFY_*` e defaults do App |
| Sessão | `%LocalAppData%\Girofy\auth.dat`, protegida por DPAPI/CurrentUser |
| Preferências | `%LocalAppData%\Girofy\preferences.json` |
| Logs | `%LocalAppData%\Girofy\logs` com rotação local |
| Instância única | mutex `Local\Girofy.Desktop.SingleInstance` |
| Workflow | `.github/workflows/build-windows-wpf.yml` em `windows-latest` |

O publish inclui `Girofy.exe` e `appsettings.json`. Recursos XAML e imagens configuradas como `Resource` são incorporados ao assembly. Nenhum runtime externo, Python ou banco acompanha o instalador.

## Tecnologia escolhida

Foi escolhido o **Inno Setup 6**.

### Motivos

- produz o `.exe` solicitado;
- é maduro e simples para um aplicativo WPF unpackaged;
- suporta instalação por usuário sem elevação;
- cria atalhos e entrada de desinstalação do Windows;
- permite upgrade por `AppId` persistente;
- integra-se ao GitHub Actions com `ISCC.exe`;
- aceita Code Signing em uma evolução futura;
- mantém o publish self-contained/single-file atual intacto.

### Alternativas consideradas

**WiX Toolset:** oferece MSI, patches e Burn, além de integração robusta com MSBuild. Para a preview atual, exigiria mais XML, conceitos de componentes/upgrade e manutenção do que o necessário. Continua viável caso surjam requisitos corporativos de MSI.

**MSIX:** fornece identidade, atualização e desinstalação controladas, porém pacotes distribuídos fora da Store precisam de uma cadeia de confiança de assinatura. Também impõe outro modelo de empacotamento e virtualização. Isso conflita com a meta atual de validar rapidamente um Setup `.exe` sem Code Signing comercial.

### Trade-offs e limitações

- o instalador preview não é assinado e pode acionar SmartScreen;
- Inno Setup não fornece sozinho o protocolo de auto-update do App;
- o canal comercial futuro precisa assinar primeiro o executável e depois o Setup;
- o teste funcional de instalação exige Windows real/VM.

Referências oficiais consideradas: [Inno Setup](https://jrsoftware.org/isinfo.php), [WiX Toolset](https://docs.firegiant.com/wix/) e [empacotamento MSIX](https://learn.microsoft.com/windows/msix/desktop/desktop-to-uwp-packaging-dot-net).

## Versionamento e metadados

A fonte de verdade é `desktop_wpf/Directory.Build.props`, que define `Version` como `0.8.0`, além de `AssemblyVersion`, `FileVersion` e `InformationalVersion`. O workflow lê essa versão, o script confere a versão publicada no `Girofy.exe` e o Inno Setup usa o mesmo valor no produto e no nome do arquivo.

Metadados visíveis:

- produto e título: `GiroFy`;
- descrição: `Sistema de gestão e ponto de venda GiroFy`;
- executável: `Girofy.exe` para preservar compatibilidade;
- instalador: `GiroFy-Setup-0.8.0.exe`;
- ícone: `desktop_wpf/src/Girofy.Desktop/Resources/Girofy.ico`.

Não foi definido Publisher, CNPJ ou empresa inexistente.

## Build

Executar em Windows com .NET 8 SDK:

```powershell
dotnet restore .\desktop_wpf\Girofy.Desktop.sln

dotnet test .\desktop_wpf\tests\Girofy.UnitTests\Girofy.UnitTests.csproj `
  --configuration Release --no-restore

dotnet publish .\desktop_wpf\src\Girofy.Desktop\Girofy.Desktop.csproj `
  --configuration Release --runtime win-x64 --self-contained true `
  -p:PublishSingleFile=true `
  -p:IncludeNativeLibrariesForSelfExtract=true `
  -p:EnableCompressionInSingleFile=true `
  -p:DebugType=None `
  --output .\desktop_wpf\artifacts\Girofy-Windows-WPF
```

## Empacotamento

Entrada: `desktop_wpf/artifacts/Girofy-Windows-WPF/*`.

Definição: `desktop_wpf/installer/GiroFy.iss`.

Comando:

```powershell
.\desktop_wpf\installer\build-installer.ps1
```

O script lê a versão, encontra o publish, bloqueia arquivos indevidos, compara a versão do executável, encontra `ISCC.exe`, compila o Setup e valida nome/tamanho.

O script `desktop_wpf/installer/test-installer.ps1` executa no runner Windows um ciclo automatizado de instalação silenciosa, conferência do diretório/atalho/registro, abertura do App, instância única, desinstalação, preservação dos dados locais e reinstalação.

Saída:

```text
desktop_wpf/artifacts/installer/GiroFy-Setup-0.8.0.exe
```

## Instalação

Escopo: por usuário e sem UAC.

Diretório:

```text
%LocalAppData%\Programs\GiroFy
```

A escolha evita privilégio administrativo e mantém arquivos do programa separados dos dados mutáveis. O Setup cria atalho obrigatório no Menu Iniciar, oferece atalho opcional na Área de Trabalho e registra `GiroFy` versão `0.8.0` em Aplicativos instalados. Ao final da instalação interativa, o usuário pode abrir o App.

## Dados locais

O instalador não muda nem incorpora:

```text
%LocalAppData%\Girofy\auth.dat
%LocalAppData%\Girofy\preferences.json
%LocalAppData%\Girofy\logs\desktop.log
```

`auth.dat` continua protegido por DPAPI `CurrentUser`. Tema, usuário lembrado e preferências permanecem fora do diretório do programa.

## Desinstalação e reinstalação

A desinstalação remove os arquivos do programa, atalhos e registro do instalador. Ela preserva intencionalmente `%LocalAppData%\Girofy`, incluindo sessão protegida, preferências e logs. Logout deve ser usado quando for necessário revogar e apagar a sessão antes de desinstalar.

Ao reinstalar 0.8.0, o mesmo `AppId` e diretório são reutilizados. O Setup atualiza os binários sem depender da pasta de build original.

## Upgrade futuro

O `AppId` persistente abaixo identifica a linha do produto e não deve ser alterado arbitrariamente:

```text
4A79774E-9F9D-4CB5-84A6-69BF567BE89B
```

Versões 0.8.1, 0.9.0 e 1.0.0 devem manter esse `AppId`. Testes específicos de upgrade continuam obrigatórios.

## GitHub Actions

Workflow: `.github/workflows/build-windows-wpf.yml`.

Triggers: `workflow_dispatch`, push em `main` e pull request nos caminhos do App/contratos.

Fluxo:

```text
checkout → versão → bindings XAML → .NET/Python → contratos backend
→ restore → testes .NET → publish → Inno Setup → validações
→ artifacts → release preview
```

Artifacts temporários, com retenção de sete dias:

- `GiroFy-Windows-0.8.0` contendo `Girofy.exe`;
- `GiroFy-Installer-0.8.0` contendo `GiroFy-Setup-0.8.0.exe`.

Fora de pull requests, os dois arquivos também são enviados para a release pre-release `windows-preview`, que não é uma versão estável.

## Segurança do pacote

O script rejeita `.env`, metadados `.git`, certificados/chaves, SQLite, dumps SQL, backups, logs e nomes indicativos de credenciais/segredos. O pacote não deve conter senha, token de desenvolvimento, credencial OCI, GitHub Secret, certificado privado ou conexão MySQL.

`appsettings.json` contém somente configuração pública do cliente. O endereço atual usa HTTP de preview e não é adequado para lançamento comercial.

## Code Signing futuro

Ordem prevista:

```text
publish → assinar Girofy.exe → gerar Setup → assinar Setup → release
```

Certificado, senha e configuração de timestamp deverão vir de GitHub Secrets, cofre ou HSM. Nenhum certificado privado entra no Git.

## Auto-update futuro

Não implementado em 0.8.0. O `AppId` estável permite que uma evolução baixe um Setup assinado, valide versão/assinatura/hash, feche o App, execute upgrade e reinicie. A política de rollback ainda precisa ser definida.

## Matriz de homologação

### Automatizada no workflow

- [x] bindings XAML válidos;
- [x] contratos backend aprovados (196 testes);
- [x] restore .NET aprovado;
- [x] testes .NET aprovados (65 testes);
- [x] publish win-x64 self-contained/single-file aprovado;
- [x] versão do executável corresponde a 0.8.0;
- [x] publish sem arquivos proibidos;
- [x] instalador gerado com nome correto e tamanho válido;
- [x] instalação, abertura e instância única aprovadas no runner;
- [x] desinstalação, preservação de dados e reinstalação aprovadas no runner;
- [x] artifacts enviados;
- [x] release preview atualizada.

Evidência: workflow `Build Windows WPF` nº `32086276016`, concluído com sucesso em
18/08/2026, no commit `957192179b45d4a955a38579a438f0bc9e500b96`:
https://github.com/RafaelBG7/pdv2026/actions/runs/32086276016

O smoke test foi executado em runner Windows hospedado pelo GitHub. Ele comprova o
ciclo técnico automatizado, mas não substitui a homologação interativa em uma VM
Windows limpa representativa do computador do cliente.

### Manual em VM Windows limpa

- [ ] Setup abre e instala sem SDK/runtime;
- [ ] arquivos são instalados no diretório esperado;
- [ ] Menu Iniciar, ícone e atalho opcional funcionam;
- [ ] Aplicativos instalados exibe nome/versão/desinstalação;
- [ ] App abre, faz health check, login, refresh e logout;
- [ ] sessão DPAPI persiste para o mesmo usuário;
- [ ] tema, preferências e logs persistem;
- [ ] segunda abertura não cria outra instância;
- [ ] API indisponível e URL inválida não causam crash não tratado;
- [ ] App aberto durante desinstalação é tratado previsivelmente;
- [ ] desinstalação remove programa/atalhos e preserva dados locais;
- [ ] reinstalação funciona;
- [ ] upgrade para versão posterior funciona.

## Instalação silenciosa para teste

```powershell
.\GiroFy-Setup-0.8.0.exe /VERYSILENT /NORESTART /SUPPRESSMSGBOXES
& "$env:LOCALAPPDATA\Programs\GiroFy\unins000.exe" /VERYSILENT /NORESTART
```

## Limitações conhecidas

- sem Code Signing e reputação SmartScreen;
- sem auto-update;
- sem HTTPS/domínio comercial;
- instalação e UX ainda precisam de homologação em Windows limpo;
- publicação somente x64;
- dados locais preservados na desinstalação;
- release permanece pre-release.

## Artefatos validados em 18/08/2026

- Setup persistente da pre-release:
  `https://github.com/RafaelBG7/pdv2026/releases/download/windows-preview/GiroFy-Setup-0.8.0.exe`;
- SHA-256 do Setup publicado na release:
  `22aba860eedc34204d36d6bd1ffb2a4f77abd02c6e308c01dca2e2123f52215b`;
- tamanho do Setup publicado: `68.844.303` bytes;
- executável portátil:
  `https://github.com/RafaelBG7/pdv2026/releases/download/windows-preview/Girofy.exe`;
- SHA-256 do executável portátil:
  `11d098301de14d85eca259aa9a642f9bf004ebf761a4da5a4a40be56c371db92`;
- artifacts do workflow expiram em 25/08/2026; a pre-release é o canal persistente.

## Troubleshooting

- `ISCC.exe não encontrado`: instalar Inno Setup 6 ou informar `-IsccPath`.
- versão divergente: publicar novamente após atualizar `Directory.Build.props`.
- arquivo proibido: remover do publish, sem contornar a validação.
- cota de artifact: remover artifacts antigos e aguardar o recálculo; a release preview é o canal persistente.
- App não autentica: verificar URL, API e restrição de HTTP inseguro; nunca incorporar credenciais no Setup.

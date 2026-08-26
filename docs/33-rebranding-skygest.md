# 33 - Rebranding SkyGest

## Nome oficial

O nome oficial atual do produto é **SkyGest**. **Girofy** foi o nome utilizado
anteriormente.

O rebranding altera interfaces, mensagens públicas, e-mails, metadados, ícones,
atalhos e instalador. Regras de negócio, contratos da API e estrutura de dados
não foram alterados.

## Assets oficiais

- `app/static/brand/skygest-logo-horizontal.png`: assinatura horizontal para login;
- `app/static/brand/skygest-symbol-circle.png`: símbolo compacto para navegação;
- `app/static/brand/skygest-app-icon.png`: ícone quadrado oficial;
- `app/static/brand/favicon.ico` e `skygest-icon-*.png`: favicon, Apple Touch e PWA;
- `desktop_wpf/src/Girofy.Desktop/Resources/SkyGest.ico`: ícone multirresolução do Windows.

## Compatibilidade legada

Os identificadores abaixo continuam usando o nome anterior propositalmente:

- namespaces, nomes de projetos e caminhos-fonte `Girofy.*`;
- `%LOCALAPPDATA%\Girofy`, entropia DPAPI e nomes de mutex/pipe;
- esquema de callback `girofy://` e seu registro no Windows;
- chaves `girofy-*` no `localStorage`;
- salts de autenticação, prefixos de rate limit e nomes de serviço da API;
- variáveis `GIROFY_*`, recursos OCI e diretórios `/opt/girofy`;
- endereços de e-mail e infraestrutura existentes.

Esses nomes não são exibidos como marca ao usuário. Mantê-los evita invalidar
sessões, tokens, preferências, dados locais, callbacks, automações e produção.

## Empacotamento Windows

O executável passa a se chamar `SkyGest.exe`, e o instalador segue o padrão
`SkyGest-Setup-[VERSAO].exe`. O `AppId` do instalador permanece o mesmo para que
uma instalação anterior seja reconhecida como atualização. O diretório legado
de dados não é removido durante instalação ou desinstalação.

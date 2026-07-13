# Girofy Windows Tauri Client

Cliente desktop Windows do Girofy baseado em Tauri 2 e WebView2.

Ele abre o Girofy hospedado em:

```text
http://168.75.101.126:18080
```

O cliente não inclui Python, Flask, MySQL, `.env`, banco de dados, backups ou credenciais do servidor. Ele é apenas uma janela nativa com tela de carregamento, health check, logs locais e validação da URL permitida.

## Configuração Local

O arquivo de configuração fica em:

```text
C:\ProgramData\Girofy\config\desktop.json
```

Se o arquivo não existir, o cliente tenta criar uma configuração padrão apontando para a OCI atual.

Exemplo atual usando o IP da OCI:

```json
{
  "app_url": "http://168.75.101.126:18080",
  "allowed_hosts": ["168.75.101.126"],
  "allow_http": true,
  "environment": "development",
  "timeout_seconds": 4,
  "auto_update_enabled": false,
  "update_check_on_start": false,
  "update_manifest_url": "http://168.75.101.126:18080/desktop/update.json"
}
```

Quando houver domínio e HTTPS, altere para:

```json
{
  "app_url": "https://app.girofy.com.br",
  "allowed_hosts": ["app.girofy.com.br", ".girofy.com.br"],
  "allow_http": false,
  "environment": "production"
}
```

## Desenvolvimento

Pré-requisitos:

- Windows 10/11;
- WebView2 Runtime;
- Node.js 22 LTS ou superior;
- Rust stable via `rustup`;
- Visual Studio Build Tools com workload de C++ Desktop.

Comandos:

```powershell
cd desktop_tauri
npm install
npm test
cd src-tauri
cargo test
cargo clippy --all-targets -- -D warnings
```

Build:

```powershell
.\scripts\build_windows_tauri.ps1
```

Artefatos:

```text
dist\tauri\
```

## Logs

O cliente grava logs locais em:

```text
%LOCALAPPDATA%\Girofy\logs\tauri-client.log
```

Os logs não registram senha, token, secret ou key em texto aberto.

## Cliente Legado

O cliente antigo em `desktop_cloud/` continua preservado apenas como legado. Novas distribuições Windows cloud devem usar este cliente Tauri.

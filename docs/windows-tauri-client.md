# Cliente Windows Tauri do Girofy

Este documento descreve o cliente Windows cloud atual do Girofy, criado com **Tauri 2 + WebView2**.

## Objetivo

O cliente Tauri substitui a janela antiga baseada em Python, pywebview e PyInstaller. A nova versão foi criada para reduzir consumo local, evitar congelamentos da janela e deixar o computador do cliente responsável apenas por abrir o Girofy hospedado.

O backend Flask, MySQL, permissões, rotas, SaaS, assinatura, auditoria e deploy OCI continuam no servidor.

## O Que O Cliente Faz

- abre uma janela nativa Windows;
- carrega uma tela local de inicialização;
- lê `C:\ProgramData\Girofy\config\desktop.json`;
- valida URL, protocolo e host permitido;
- chama `/health` no servidor;
- redireciona para o Girofy hospedado quando o servidor responde;
- mostra estado offline com botão de tentar novamente quando falha;
- mantém cookies e sessão no WebView2;
- impede múltiplas instâncias desnecessárias;
- grava logs locais em `%LOCALAPPDATA%\Girofy\logs\tauri-client.log`;
- prepara a base para atualização oficial do Tauri quando o projeto tiver HTTPS, assinatura e endpoint próprio.

## O Que O Cliente Não Faz

- não instala MySQL;
- não sobe Flask local;
- não executa Python;
- não empacota backend;
- não guarda `.env`;
- não guarda senha do banco;
- não faz sincronização offline;
- não acessa o banco diretamente;
- não substitui o deploy OCI.

## Estrutura

```text
desktop_tauri/
├── index.html
├── package.json
├── src/
│   ├── main.js
│   ├── styles.css
│   ├── loading.html
│   ├── offline.html
│   └── error.html
├── tests/
│   └── frontend.test.mjs
└── src-tauri/
    ├── Cargo.toml
    ├── tauri.conf.json
    ├── capabilities/
    ├── icons/
    └── src/
        ├── config.rs
        ├── logging.rs
        ├── network.rs
        ├── security.rs
        ├── updater.rs
        ├── lib.rs
        └── main.rs
```

## Configuração

Arquivo padrão:

```text
C:\ProgramData\Girofy\config\desktop.json
```

Na primeira abertura, se esse arquivo não existir, o cliente tenta criá-lo automaticamente com a configuração temporária atual da OCI.

Configuração temporária atual com IP da OCI:

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

Quando houver domínio e HTTPS:

```json
{
  "app_url": "https://app.girofy.com.br",
  "allowed_hosts": ["app.girofy.com.br", ".girofy.com.br"],
  "allow_http": false,
  "environment": "production",
  "timeout_seconds": 4,
  "auto_update_enabled": true,
  "update_check_on_start": true
}
```

Variáveis úteis para teste:

```powershell
$env:GIROFY_DESKTOP_APP_URL="http://168.75.101.126:18080"
$env:GIROFY_DESKTOP_ALLOWED_HOSTS="168.75.101.126"
$env:GIROFY_DESKTOP_ALLOW_HTTP="1"
$env:GIROFY_DESKTOP_ENV="development"
```

## Health Check

O servidor expõe:

```text
GET /health
```

Resposta:

```json
{
  "status": "ok",
  "service": "girofy"
}
```

Esse endpoint não exige login e não revela dados sensíveis.

## Build Local

Pré-requisitos no Windows:

- Node.js 22 LTS;
- Rust stable;
- Visual Studio Build Tools;
- WebView2 Runtime.

Comando:

```powershell
.\scripts\build_windows_tauri.ps1
```

Saída:

```text
dist\tauri\
```

## GitHub Actions

Workflow:

```text
.github/workflows/build-windows-tauri-client.yml
```

Execução manual:

```text
GitHub > Actions > Build Windows Tauri client > Run workflow
```

Artefato:

```text
Girofy-Windows-Tauri-Installers
```

Tags `windows-tauri-v*` publicam Release automaticamente.

## Atualização

A estrutura `updater.rs` deixa a decisão de atualização preparada, mas a atualização oficial do Tauri deve ser ligada quando houver:

- domínio HTTPS;
- assinatura digital do instalador;
- endpoint de update compatível com Tauri;
- chave pública do updater configurada.

Até lá, distribua novos instaladores pelos artifacts ou Releases do GitHub.

## Segurança

- URLs `file://`, `javascript:` e protocolos desconhecidos são bloqueados pela camada de validação.
- HTTP só é aceito quando `allow_http=true`.
- Hosts precisam estar em `allowed_hosts`.
- Logs mascaram `password=`, `token=`, `secret=` e `key=`.
- O cliente não contém credenciais do servidor.
- A API Tauri exposta ao frontend contém apenas comandos de configuração pública, health check e log local.

## Cliente Legado

O cliente antigo em `desktop_cloud/`, `desktop_cloud_launcher.py`, `girofy-cloud.spec`, `installer/cloud/` e `scripts/build_windows_cloud.ps1` continua no repositório como legado, mas não é mais recomendado para novas instalações.

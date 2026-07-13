# Plano de Testes do Cliente Windows Tauri

## Testes Automatizados

Backend:

```powershell
python -m unittest discover
```

Frontend local do cliente:

```powershell
cd desktop_tauri
npm ci
npm test
```

Rust:

```powershell
cd desktop_tauri\src-tauri
cargo fmt --check
cargo test
cargo clippy --all-targets -- -D warnings
```

## Cenários Manuais Obrigatórios

### Inicialização Online

1. Criar `C:\ProgramData\Girofy\config\desktop.json` apontando para `http://168.75.101.126:18080`.
2. Abrir o cliente.
3. Confirmar tela de carregamento.
4. Confirmar abertura da tela de login do Girofy.
5. Entrar com usuário válido.
6. Fechar e abrir novamente.
7. Confirmar que sessão/cookies continuam funcionando conforme regra do servidor.

### Inicialização Offline

1. Desconectar internet ou apontar `app_url` para host inválido.
2. Abrir o cliente.
3. Confirmar que a janela não congela.
4. Confirmar mensagem de falha.
5. Clicar em `Tentar novamente`.

### Configuração Inválida

1. Usar `app_url` com `javascript:` ou `file://`.
2. Abrir o cliente.
3. Confirmar bloqueio e log local.

### Host Não Permitido

1. Configurar `app_url` com domínio fora de `allowed_hosts`.
2. Abrir o cliente.
3. Confirmar bloqueio.

### Responsividade

1. Abrir em 1366x768.
2. Maximizar.
3. Reduzir para 1024x640.
4. Confirmar que carregamento/offline não cortam textos.

### WebView2

1. Testar em Windows 10/11 com WebView2 instalado.
2. Testar em máquina sem WebView2, validando se o instalador solicita/baixa o runtime.

### Consumo

1. Abrir Gerenciador de Tarefas.
2. Iniciar Girofy.
3. Confirmar que não há processo Python, Flask ou MySQL iniciado pelo cliente Tauri.
4. Confirmar que o consumo fica concentrado no processo WebView2/Tauri.

## Critérios de Aprovação

- Cliente abre sem travar.
- Offline mostra tela amigável.
- Config inválida não navega.
- Não existe Python/PyInstaller no novo pacote.
- `/health` responde sem autenticação.
- Build gera `.exe`/`.msi`.
- Logs locais são criados sem dados sensíveis.

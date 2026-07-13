# Girofy Windows Cloud Client

O cliente Windows cloud do Girofy é um aplicativo desktop leve que abre a versão hospedada do sistema dentro de uma janela nativa via `pywebview`.

Ele não instala banco local, não sobe Flask local, não conecta no MySQL diretamente e não possui sincronização offline.

> A versão desktop cloud do Girofy depende integralmente de conexão com a internet. Nenhum dado operacional é armazenado localmente.

## Arquitetura

Fluxo de execução:

1. `Girofy.exe` inicia `desktop_cloud_launcher.py`.
2. O launcher impede múltiplas instâncias desnecessárias.
3. Carrega `C:\ProgramData\Girofy\config\desktop.json`.
4. Valida URL, protocolo e domínio permitido.
5. Testa conectividade com o servidor hospedado.
6. Abre a janela nativa do Girofy.
7. O usuário usa o mesmo app web hospedado, com login, permissões, CSRF, auditoria e cookies do servidor.

O executável não inclui:

- `.env`;
- senha MySQL;
- `SECRET_KEY`;
- credenciais SMTP;
- banco local;
- backups;
- logs do servidor;
- código do backend Flask.

## Configuração da URL

Configuração padrão instalada em:

```text
C:\ProgramData\Girofy\config\desktop.json
```

Exemplo para produção futura com domínio e HTTPS:

```json
{
  "app_url": "https://app.girofy.com.br",
  "allowed_hosts": ["app.girofy.com.br", ".girofy.com.br"],
  "allow_http": false,
  "environment": "production"
}
```

Em produção:

- `app_url` precisa usar `https://`;
- certificado TLS normal precisa ser válido;
- domínio precisa estar na allowlist;
- `file://`, `javascript:` e domínios desconhecidos são bloqueados.

Configuração temporária atual, enquanto o domínio ainda não existe:

```json
{
  "app_url": "http://168.75.101.126:18080",
  "allowed_hosts": ["168.75.101.126"],
  "allow_http": true,
  "environment": "development"
}
```

Essa configuração usa HTTP porque a aplicação ainda está acessível apenas pelo IP da OCI. Quando o domínio existir, volte para `environment: "production"` e `allow_http: false`.

Para desenvolvimento temporário com a VM atual:

```powershell
$env:GIROFY_DESKTOP_ENV="development"
$env:GIROFY_DESKTOP_ALLOW_HTTP="1"
$env:GIROFY_DESKTOP_APP_URL="http://168.75.101.126:18080"
$env:GIROFY_DESKTOP_ALLOWED_HOSTS="168.75.101.126"
.\desktop_cloud_launcher.py
```

## Logs Locais

Logs do launcher ficam em:

```text
C:\ProgramData\Girofy\logs\launcher.log
```

Eles registram início, versão, teste de conectividade, falha de domínio, servidor indisponível e encerramento inesperado.

Os logs não registram senhas, cookies, tokens, conteúdo de formulários ou dados de venda.

## Tela Sem Conexão

Se a internet ou o servidor estiver indisponível, o app mostra uma tela local com:

- logo Girofy;
- mensagem amigável;
- botão `Tentar novamente`;
- botão `Fechar`;
- status simples da tentativa.

Essa tela não armazena dados operacionais.

## Desenvolvimento Local

Instale as dependências do cliente:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop-cloud.txt
```

Execute:

```powershell
$env:GIROFY_DESKTOP_ENV="development"
$env:GIROFY_DESKTOP_ALLOW_HTTP="1"
$env:GIROFY_DESKTOP_APP_URL="http://168.75.101.126:18080"
$env:GIROFY_DESKTOP_ALLOWED_HOSTS="168.75.101.126"
.\.venv\Scripts\python.exe desktop_cloud_launcher.py
```

## Gerar o EXE

No Windows:

```powershell
.\scripts\build_windows_cloud.ps1
```

Saída:

```text
dist\Girofy\Girofy.exe
```

## Gerar o Instalador

Instale o Inno Setup e rode:

```powershell
$env:APP_VERSION="1.0.0"
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" installer\cloud\GirofyCloud.iss
```

Saída:

```text
dist\installer\Girofy-Setup.exe
```

O instalador:

- instala em `C:\Program Files\Girofy`;
- cria atalho no menu iniciar;
- pode criar atalho na área de trabalho;
- preserva `desktop.json`;
- não instala MySQL;
- não abre portas no firewall.

## GitHub Actions

Workflow:

```text
.github/workflows/build-windows-cloud-client.yml
```

Execução manual:

```text
GitHub > Actions > Build Windows cloud client > Run workflow
```

Execução por tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Artefatos:

- `Girofy-Windows-Cloud.zip`;
- `Girofy-Setup.exe`.

Em tags `v*`, o workflow cria uma Release automática.

## Testes

Rodar testes do cliente:

```bash
python -m unittest tests.test_desktop_cloud
```

Rodar tudo:

```bash
python -m unittest discover
```

## Downloads e Uploads

O app usa a sessão web normal do Girofy. Upload de CSV/XLSX, download de modelo, exportações e backups autorizados continuam passando pelo servidor web.

O `pywebview` é configurado para permitir downloads. Caso algum backend nativo do Windows tenha limitação com downloads específicos, a correção deve ser feita de forma pontual sem salvar credenciais no cliente.

## Segurança

Mantido no servidor:

- login;
- CSRF;
- permissões;
- isolamento por adega;
- auditoria;
- headers de segurança;
- cookies e sessão.

Aplicado no cliente:

- validação de URL;
- HTTPS obrigatório em produção;
- allowlist de domínio;
- bloqueio de `file://` e `javascript:`;
- abertura externa de links fora da allowlist;
- logs sanitizados;
- instância única;
- sem armazenamento de senha.

## Assinatura Digital

O workflow chama `scripts/sign_windows_artifacts.ps1`. Para reduzir alertas do SmartScreen em distribuição real, configure os secrets de assinatura:

```text
WINDOWS_CODESIGN_PFX_BASE64
WINDOWS_CODESIGN_PFX_PASSWORD
WINDOWS_CODESIGN_TIMESTAMP_URL
```

Sem certificado reconhecido, o Windows pode continuar exibindo alerta de app não confiável.

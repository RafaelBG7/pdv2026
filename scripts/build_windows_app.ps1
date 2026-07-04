$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Virtualenv não encontrado em $RootDir\.venv"
    Write-Host "Crie o venv e instale as dependências antes de compilar."
    exit 1
}

Set-Location $RootDir

& $VenvPython -m pip install -r requirements.txt -r requirements-build.txt

Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist\GirofyPDV -ErrorAction SilentlyContinue

& $VenvPython -m PyInstaller `
    --name GirofyPDV `
    --windowed `
    --onedir `
    --clean `
    --add-data "app/templates;app/templates" `
    --add-data "app/static;app/static" `
    --hidden-import pymysql `
    --hidden-import webview `
    --hidden-import webview.platforms.edgechromium `
    --hidden-import webview.platforms.winforms `
    desktop_launcher.py

if (Test-Path ".env") {
    Copy-Item ".env" "dist\.env" -Force
    Write-Host "Configuração local copiada para dist\.env"
} elseif (Test-Path ".env.example") {
    Copy-Item ".env.example" "dist\.env.example" -Force
    Write-Host "Nenhum .env encontrado. Modelo copiado para dist\.env.example"
} else {
    @"
APP_ENV=desktop
FLASK_DEBUG=0
SECRET_KEY=troque-esta-chave
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=adega_central
MAIL_SUPPRESS_SEND=1
PORT=5003
"@ | Set-Content -Path "dist\.env.example" -Encoding UTF8
    Write-Host "Nenhum .env encontrado. Modelo mínimo criado em dist\.env.example"
}

Write-Host ""
Write-Host "Aplicativo gerado em:"
Write-Host "  $RootDir\dist\GirofyPDV\GirofyPDV.exe"

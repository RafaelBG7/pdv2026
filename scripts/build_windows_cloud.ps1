$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Virtualenv não encontrado em $RootDir\.venv"
    Write-Host "Crie o venv e instale as dependências antes de compilar."
    exit 1
}

Set-Location $RootDir

& $VenvPython -m pip install -r requirements-desktop-cloud.txt

$IconSource = Join-Path $RootDir "app\static\favicon-v2.png"
$IconOutput = Join-Path $RootDir "desktop_cloud\resources\girofy.ico"
& $VenvPython -c "from PIL import Image; img=Image.open(r'$IconSource').convert('RGBA'); img.save(r'$IconOutput', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"

Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist\Girofy -ErrorAction SilentlyContinue

$SpecFile = Join-Path $RootDir "girofy-cloud.spec"
if (-not (Test-Path $SpecFile)) {
    Write-Host "Arquivo de spec do PyInstaller não encontrado:"
    Write-Host "  $SpecFile"
    Write-Host "Arquivos disponíveis na raiz do projeto:"
    Get-ChildItem $RootDir | Select-Object -ExpandProperty Name
    exit 1
}

& $VenvPython -m PyInstaller $SpecFile --clean --noconfirm

Write-Host ""
Write-Host "Cliente cloud gerado em:"
Write-Host "  $RootDir\dist\Girofy\Girofy.exe"

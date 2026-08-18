[CmdletBinding()]
param(
    [string]$Version,
    [string]$PublishDir = (Join-Path $PSScriptRoot '..\artifacts\Girofy-Windows-WPF'),
    [string]$OutputDir = (Join-Path $PSScriptRoot '..\artifacts\installer'),
    [string]$IsccPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$desktopRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$propsPath = Join-Path $desktopRoot 'Directory.Build.props'
$installerScript = Join-Path $PSScriptRoot 'GiroFy.iss'

if ([string]::IsNullOrWhiteSpace($Version)) {
    [xml]$props = Get-Content -Raw $propsPath
    $versionNode = $props.SelectSingleNode('/Project/PropertyGroup/Version')
    if ($null -eq $versionNode -or [string]::IsNullOrWhiteSpace($versionNode.InnerText)) {
        throw "Version não encontrada em $propsPath"
    }
    $Version = $versionNode.InnerText.Trim()
}

if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Version deve usar o formato MAJOR.MINOR.PATCH. Recebido: $Version"
}

$resolvedPublishDir = (Resolve-Path $PublishDir).Path
$executable = Join-Path $resolvedPublishDir 'Girofy.exe'
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Executável publicado não encontrado: $executable"
}

$forbiddenPatterns = @(
    '.env', '.git', '*.pfx', '*.pem', '*.key', '*.sqlite', '*.sqlite3',
    '*.db', '*.sql', '*.bak', '*.log', '*id_rsa*', '*credentials*', '*secret*'
)
$forbiddenFiles = foreach ($pattern in $forbiddenPatterns) {
    Get-ChildItem -LiteralPath $resolvedPublishDir -Recurse -Force -File -Filter $pattern
}
if ($forbiddenFiles) {
    $paths = ($forbiddenFiles.FullName | Sort-Object -Unique) -join [Environment]::NewLine
    throw "Conteúdo proibido encontrado no publish:$([Environment]::NewLine)$paths"
}

$publishedVersion = (Get-Item -LiteralPath $executable).VersionInfo.ProductVersion
if ([string]::IsNullOrWhiteSpace($publishedVersion) -or -not $publishedVersion.StartsWith($Version)) {
    throw "Versão do Girofy.exe ($publishedVersion) não corresponde ao instalador ($Version)."
}

if ([string]::IsNullOrWhiteSpace($IsccPath)) {
    $isccCommand = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($null -ne $isccCommand) {
        $IsccPath = $isccCommand.Source
    }
    else {
        $defaultPaths = @(
            (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
            (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
        }
        $IsccPath = $defaultPaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
}

if ([string]::IsNullOrWhiteSpace($IsccPath) -or -not (Test-Path -LiteralPath $IsccPath)) {
    throw 'ISCC.exe não encontrado. Instale o Inno Setup 6 ou informe -IsccPath.'
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$resolvedOutputDir = (Resolve-Path $OutputDir).Path

& $IsccPath `
    "/DAppVersion=$Version" `
    "/DPublishDir=$resolvedPublishDir" `
    "/DOutputDir=$resolvedOutputDir" `
    $installerScript

if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup encerrou com código $LASTEXITCODE."
}

$installer = Join-Path $resolvedOutputDir "GiroFy-Setup-$Version.exe"
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "Instalador esperado não foi gerado: $installer"
}

$installerInfo = Get-Item -LiteralPath $installer
if ($installerInfo.Length -lt 1MB) {
    throw "Instalador possui tamanho inesperado: $($installerInfo.Length) bytes."
}

Write-Host "Instalador gerado: $($installerInfo.FullName)"
Write-Host "Tamanho: $($installerInfo.Length) bytes"

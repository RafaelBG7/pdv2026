[CmdletBinding()]
param(
    [string]$Version,
    [string]$InstallerPath = (Join-Path $PSScriptRoot "..\artifacts\installer\GiroFy-Setup-$Version.exe")
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($Version) -or $Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Version inválida: $Version"
}

$installer = (Resolve-Path $InstallerPath).Path
$installDir = Join-Path $env:LOCALAPPDATA 'Programs\GiroFy'
$installedExe = Join-Path $installDir 'Girofy.exe'
$startMenuShortcut = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\GiroFy.lnk'
$dataDir = Join-Path $env:LOCALAPPDATA 'Girofy'
$preservationMarker = Join-Path $dataDir 'installer-smoke.marker'
$uninstallRegistryRoots = @(
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
    'HKCU:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'
)

function Invoke-Installer {
    $process = Start-Process -FilePath $installer -ArgumentList @(
        '/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES', '/SP-'
    ) -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Setup encerrou com código $($process.ExitCode)."
    }
}

function Get-GiroFyUninstallEntry {
    foreach ($root in $uninstallRegistryRoots) {
        if (-not (Test-Path $root)) {
            continue
        }
        $entry = Get-ChildItem $root |
            Get-ItemProperty |
            Where-Object { $_.DisplayName -eq 'GiroFy' } |
            Select-Object -First 1
        if ($null -ne $entry) {
            return $entry
        }
    }
    return $null
}

function Assert-Installed {
    if (-not (Test-Path -LiteralPath $installedExe -PathType Leaf)) {
        throw "Executável instalado não encontrado: $installedExe"
    }
    if (-not (Test-Path -LiteralPath $startMenuShortcut -PathType Leaf)) {
        throw "Atalho do Menu Iniciar não encontrado: $startMenuShortcut"
    }
    $entry = Get-GiroFyUninstallEntry
    if ($null -eq $entry) {
        throw 'GiroFy não foi registrado em Aplicativos instalados.'
    }
    if ($entry.DisplayVersion -ne $Version) {
        throw "Versão registrada ($($entry.DisplayVersion)) difere de $Version."
    }
}

function Stop-GiroFyProcesses {
    Get-Process -Name 'Girofy' -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}

function Assert-AppStartsAndIsSingleInstance {
    $first = Start-Process -FilePath $installedExe -PassThru
    Start-Sleep -Seconds 5
    $first.Refresh()
    if ($first.HasExited) {
        throw "GiroFy instalado encerrou durante a inicialização com código $($first.ExitCode)."
    }

    $second = Start-Process -FilePath $installedExe -PassThru
    if (-not $second.WaitForExit(10000)) {
        Stop-Process -Id $second.Id -Force -ErrorAction SilentlyContinue
        throw 'A segunda abertura não encerrou como esperado pelo controle de instância única.'
    }

    $running = @(Get-Process -Name 'Girofy' -ErrorAction SilentlyContinue)
    if ($running.Count -ne 1) {
        throw "Quantidade inesperada de processos Girofy após segunda abertura: $($running.Count)."
    }

    Stop-GiroFyProcesses
}

function Invoke-Uninstaller {
    Stop-GiroFyProcesses
    $uninstaller = Join-Path $installDir 'unins000.exe'
    if (-not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) {
        throw "Desinstalador não encontrado: $uninstaller"
    }
    $process = Start-Process -FilePath $uninstaller -ArgumentList @(
        '/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES'
    ) -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Desinstalador encerrou com código $($process.ExitCode)."
    }
    if (Test-Path -LiteralPath $installedExe) {
        throw 'Girofy.exe permaneceu após a desinstalação.'
    }
    if (Test-Path -LiteralPath $startMenuShortcut) {
        throw 'Atalho do Menu Iniciar permaneceu após a desinstalação.'
    }
    if ($null -ne (Get-GiroFyUninstallEntry)) {
        throw 'Registro de Aplicativos instalados permaneceu após a desinstalação.'
    }
}

try {
    Invoke-Installer
    Assert-Installed
    Assert-AppStartsAndIsSingleInstance

    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
    Set-Content -LiteralPath $preservationMarker -Value 'preserve-on-uninstall'
    Invoke-Uninstaller
    if (-not (Test-Path -LiteralPath $preservationMarker -PathType Leaf)) {
        throw 'A desinstalação removeu indevidamente os dados locais do usuário.'
    }

    Invoke-Installer
    Assert-Installed
    Assert-AppStartsAndIsSingleInstance
    Invoke-Uninstaller

    Write-Host 'Smoke test de instalação, abertura, instância única, desinstalação e reinstalação aprovado.'
}
finally {
    Stop-GiroFyProcesses
    if (Test-Path -LiteralPath (Join-Path $installDir 'unins000.exe')) {
        try { Invoke-Uninstaller } catch { Write-Warning $_ }
    }
    Remove-Item -LiteralPath $preservationMarker -Force -ErrorAction SilentlyContinue
}

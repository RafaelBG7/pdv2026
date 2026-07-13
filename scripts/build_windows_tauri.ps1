param(
    [string]$Configuration = "release"
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ClientDir = Join-Path $RootDir "desktop_tauri"
$OutputDir = Join-Path $RootDir "dist\tauri"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js nao encontrado. Instale Node.js 22 LTS ou superior."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm nao encontrado."
}

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "Rust/Cargo nao encontrado. Instale via https://rustup.rs/."
}

Push-Location $ClientDir
try {
    if (Test-Path ".\package-lock.json") {
        npm ci
    }
    else {
        npm install
    }
    npm test
    cargo fmt --manifest-path ".\src-tauri\Cargo.toml" --check
    cargo test --manifest-path ".\src-tauri\Cargo.toml"
    cargo clippy --manifest-path ".\src-tauri\Cargo.toml" --all-targets -- -D warnings
    npm run tauri build
}
finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$BundleDir = Join-Path $ClientDir "src-tauri\target\$Configuration\bundle"
$Artifacts = @()
if (Test-Path $BundleDir) {
    $Artifacts = Get-ChildItem $BundleDir -Recurse -Include *.exe, *.msi | Where-Object { -not $_.PSIsContainer }
}

if (-not $Artifacts -or $Artifacts.Count -eq 0) {
    throw "Nenhum instalador Tauri foi encontrado em $BundleDir."
}

$HashLines = @()
foreach ($Artifact in $Artifacts) {
    $Destination = Join-Path $OutputDir $Artifact.Name
    Copy-Item $Artifact.FullName $Destination -Force
    $Hash = Get-FileHash $Destination -Algorithm SHA256
    $HashLines += "$($Hash.Hash.ToLower())  $($Artifact.Name)"
    Write-Host "Artefato gerado: $Destination"
}

$HashFile = Join-Path $OutputDir "SHA256SUMS.txt"
$HashLines | Set-Content -Path $HashFile -Encoding ASCII
Write-Host "Hashes gravados em: $HashFile"

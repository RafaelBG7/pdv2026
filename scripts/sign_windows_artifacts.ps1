$ErrorActionPreference = "Stop"

$CertBase64 = $env:WINDOWS_CODESIGN_PFX_BASE64
$CertPassword = $env:WINDOWS_CODESIGN_PFX_PASSWORD
$TimestampUrl = if ($env:WINDOWS_CODESIGN_TIMESTAMP_URL) { $env:WINDOWS_CODESIGN_TIMESTAMP_URL } else { "http://timestamp.digicert.com" }

if ([string]::IsNullOrWhiteSpace($CertBase64) -or [string]::IsNullOrWhiteSpace($CertPassword)) {
    Write-Host "Certificado Windows não configurado. Pulando assinatura."
    exit 0
}

$CertPath = Join-Path $env:RUNNER_TEMP "girofy-codesign.pfx"
[IO.File]::WriteAllBytes($CertPath, [Convert]::FromBase64String($CertBase64))

$signtool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Recurse -Filter signtool.exe |
    Where-Object { $_.FullName -match "\\x64\\signtool\.exe$" } |
    Sort-Object FullName -Descending |
    Select-Object -First 1

if (-not $signtool) {
    throw "signtool.exe não encontrado. Instale o Windows SDK no runner."
}

$targets = @(
    "dist\Girofy\Girofy.exe",
    "dist\installer\Girofy-Setup.exe"
)

foreach ($target in $targets) {
    if (-not (Test-Path $target)) {
        Write-Host "Arquivo não encontrado para assinatura: $target"
        continue
    }

    & $signtool.FullName sign `
        /f $CertPath `
        /p $CertPassword `
        /fd SHA256 `
        /tr $TimestampUrl `
        /td SHA256 `
        /d "Girofy" `
        /v `
        $target

    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao assinar $target."
    }

    & $signtool.FullName verify /pa /v $target
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao verificar assinatura de $target."
    }
}

Remove-Item $CertPath -Force -ErrorAction SilentlyContinue

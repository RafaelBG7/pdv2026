$ErrorActionPreference = "Stop"

$ServiceName = "GirofyMySQL"

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service) {
    if ($service.Status -ne "Stopped") {
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    sc.exe delete $ServiceName | Out-Null
}

# Os dados ficam em C:\ProgramData\Girofy para evitar remoção acidental
# de vendas, produtos e caixas durante uma desinstalação comum.

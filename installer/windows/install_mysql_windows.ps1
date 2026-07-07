param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir
)

$ErrorActionPreference = "Stop"

$ServiceName = "GirofyMySQL"
$DatabaseName = "adega_central"
$DatabaseUser = "girofy_app"
$DatabaseHost = "127.0.0.1"
$DatabasePort = 3307
$ProgramDataDir = Join-Path $env:ProgramData "Girofy"
$DataDir = Join-Path $ProgramDataDir "mysql-data"
$LogDir = Join-Path $ProgramDataDir "logs"
$SecretsDir = Join-Path $ProgramDataDir "secrets"
$MySqlDir = Join-Path $InstallDir "mysql"
$MySqlZip = Join-Path $InstallDir "installer\mysql.zip"
$MyIni = Join-Path $ProgramDataDir "my.ini"
$EnvPath = Join-Path $InstallDir ".env"
$RootPasswordPath = Join-Path $SecretsDir "mysql-root-password.txt"
$AppPasswordPath = Join-Path $SecretsDir "mysql-app-password.txt"
$SecretKeyPath = Join-Path $SecretsDir "flask-secret-key.txt"

function New-SecureText([int]$Length = 32) {
    $alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789_-"
    $bytes = New-Object byte[] $Length
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $chars = for ($i = 0; $i -lt $Length; $i++) {
        $alphabet[$bytes[$i] % $alphabet.Length]
    }
    -join $chars
}

function Get-OrCreateSecret([string]$Path, [int]$Length = 32) {
    if (Test-Path $Path) {
        return (Get-Content $Path -Raw).Trim()
    }
    $secret = New-SecureText -Length $Length
    Set-Content -Path $Path -Value $secret -Encoding UTF8
    return $secret
}

function ConvertTo-MySqlLiteral([string]$Value) {
    return $Value.Replace("\", "\\").Replace("'", "''")
}

function Invoke-MySqlRoot([string]$Sql, [string]$RootPassword = "") {
    $mysqlExe = Join-Path $MySqlDir "bin\mysql.exe"
    $tempSql = Join-Path $env:TEMP ("girofy-mysql-" + [Guid]::NewGuid().ToString("N") + ".sql")
    Set-Content -Path $tempSql -Value $Sql -Encoding UTF8
    try {
        $args = @("--host=$DatabaseHost", "--port=$DatabasePort", "--user=root", "--protocol=tcp", "--batch", "--execute=source $tempSql")
        if ($RootPassword) {
            $args = @("--host=$DatabaseHost", "--port=$DatabasePort", "--user=root", "--password=$RootPassword", "--protocol=tcp", "--batch", "--execute=source $tempSql")
        }
        & $mysqlExe @args
    } finally {
        Remove-Item $tempSql -Force -ErrorAction SilentlyContinue
    }
}

function Wait-MySqlReady([string]$RootPassword = "") {
    $mysqladminExe = Join-Path $MySqlDir "bin\mysqladmin.exe"
    for ($i = 0; $i -lt 60; $i++) {
        $args = @("--host=$DatabaseHost", "--port=$DatabasePort", "--user=root", "--protocol=tcp", "ping")
        if ($RootPassword) {
            $args = @("--host=$DatabaseHost", "--port=$DatabasePort", "--user=root", "--password=$RootPassword", "--protocol=tcp", "ping")
        }
        & $mysqladminExe @args *> $null
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "MySQL local não respondeu na porta $DatabasePort."
}

function Expand-MySqlZip() {
    if (Test-Path (Join-Path $MySqlDir "bin\mysqld.exe")) {
        return
    }
    if (-not (Test-Path $MySqlZip)) {
        throw "Pacote MySQL não encontrado em $MySqlZip."
    }

    $tempExtract = Join-Path $env:TEMP ("girofy-mysql-extract-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tempExtract -Force | Out-Null
    try {
        Expand-Archive -Path $MySqlZip -DestinationPath $tempExtract -Force
        $inner = Get-ChildItem $tempExtract -Directory | Select-Object -First 1
        if (-not $inner) {
            throw "O pacote MySQL não possui a pasta esperada."
        }
        if (Test-Path $MySqlDir) {
            Remove-Item $MySqlDir -Recurse -Force
        }
        Move-Item $inner.FullName $MySqlDir
    } finally {
        Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Write-MyIni() {
    $escapedBase = $MySqlDir.Replace("\", "/")
    $escapedData = $DataDir.Replace("\", "/")
    $escapedLog = (Join-Path $LogDir "mysql-error.log").Replace("\", "/")
    $content = @"
[mysqld]
basedir=$escapedBase
datadir=$escapedData
port=$DatabasePort
bind-address=$DatabaseHost
mysqlx=0
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
log-error=$escapedLog

[client]
host=$DatabaseHost
port=$DatabasePort
protocol=tcp
"@
    Set-Content -Path $MyIni -Value $content -Encoding ASCII
}

function Ensure-MySqlService() {
    $mysqldExe = Join-Path $MySqlDir "bin\mysqld.exe"
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $service) {
        & $mysqldExe --install $ServiceName "--defaults-file=$MyIni"
        if ($LASTEXITCODE -ne 0) {
            throw "Falha ao instalar o serviço $ServiceName."
        }
    }

    $service = Get-Service -Name $ServiceName
    if ($service.Status -ne "Running") {
        Start-Service -Name $ServiceName
    }
}

function Initialize-DataDirectory() {
    $mysqldExe = Join-Path $MySqlDir "bin\mysqld.exe"
    if ((Test-Path $DataDir) -and (Get-ChildItem $DataDir -Force -ErrorAction SilentlyContinue | Select-Object -First 1)) {
        return $false
    }

    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
    & $mysqldExe "--defaults-file=$MyIni" --initialize-insecure --console
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao inicializar os dados do MySQL."
    }
    return $true
}

function Write-AppEnv([string]$AppPassword, [string]$SecretKey) {
    $encodedPassword = [uri]::EscapeDataString($AppPassword)
    $content = @"
APP_ENV=desktop
FLASK_DEBUG=0
SECRET_KEY=$SecretKey
MASTER_DEFAULT_USERNAME=master
MASTER_DEFAULT_PASSWORD=master123
PASSWORD_MIN_LENGTH=8

MYSQL_USER=$DatabaseUser
MYSQL_PASSWORD=$AppPassword
MYSQL_HOST=$DatabaseHost
MYSQL_PORT=$DatabasePort
MYSQL_DATABASE=$DatabaseName
MYSQL_TENANT_DATABASE_PREFIX=adega
MYSQL_TENANT_DATABASE_URL_TEMPLATE=
MYSQL_SERVER_DATABASE_URL=mysql+pymysql://$DatabaseUser`:$encodedPassword@$DatabaseHost`:$DatabasePort/mysql?charset=utf8mb4

MAIL_SUPPRESS_SEND=1
PUBLIC_BASE_URL=http://127.0.0.1:5003
PORT=5003
"@
    Set-Content -Path $EnvPath -Value $content -Encoding UTF8
}

New-Item -ItemType Directory -Path $ProgramDataDir, $LogDir, $SecretsDir -Force | Out-Null
Expand-MySqlZip
Write-MyIni
$createdDataDir = Initialize-DataDirectory
Ensure-MySqlService

$rootPassword = ""
if (Test-Path $RootPasswordPath) {
    $rootPassword = (Get-Content $RootPasswordPath -Raw).Trim()
}

if ($createdDataDir) {
    Wait-MySqlReady
} else {
    Wait-MySqlReady -RootPassword $rootPassword
}

$appPassword = Get-OrCreateSecret -Path $AppPasswordPath -Length 32
$secretKey = Get-OrCreateSecret -Path $SecretKeyPath -Length 48
$appPasswordSql = ConvertTo-MySqlLiteral $appPassword

$setupSql = @"
CREATE DATABASE IF NOT EXISTS $DatabaseName CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$DatabaseUser'@'$DatabaseHost' IDENTIFIED BY '$appPasswordSql';
CREATE USER IF NOT EXISTS '$DatabaseUser'@'localhost' IDENTIFIED BY '$appPasswordSql';
ALTER USER '$DatabaseUser'@'$DatabaseHost' IDENTIFIED BY '$appPasswordSql';
ALTER USER '$DatabaseUser'@'localhost' IDENTIFIED BY '$appPasswordSql';
GRANT ALL PRIVILEGES ON *.* TO '$DatabaseUser'@'$DatabaseHost';
GRANT ALL PRIVILEGES ON *.* TO '$DatabaseUser'@'localhost';
FLUSH PRIVILEGES;
"@

Invoke-MySqlRoot -Sql $setupSql -RootPassword $rootPassword

if (-not $rootPassword) {
    $rootPassword = Get-OrCreateSecret -Path $RootPasswordPath -Length 32
    $rootPasswordSql = ConvertTo-MySqlLiteral $rootPassword
    Invoke-MySqlRoot -Sql "ALTER USER 'root'@'localhost' IDENTIFIED BY '$rootPasswordSql'; FLUSH PRIVILEGES;"
}

Write-AppEnv -AppPassword $appPassword -SecretKey $secretKey

param([switch]$InstallSqlServer)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

if ($InstallSqlServer) {
    winget install --id Microsoft.SQLServer.2025.Express --exact --source winget --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw 'SQL Server installation failed. Install Express and retry.'
    }
    winget install --id Microsoft.msodbcsql.18 --exact --source winget --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw 'ODBC Driver 18 installation failed.'
    }
}

$pythonExe = $env:SILICONWATCH_PYTHON
if (!$pythonExe) { $pythonExe = 'python' }
if (!(Get-Command $pythonExe -ErrorAction SilentlyContinue)) {
    throw 'Install Python 3.11+ or set SILICONWATCH_PYTHON to its executable path.'
}
if (!(Get-Command node -ErrorAction SilentlyContinue) -or !(Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'Install Node.js 22+ with npm and add it to PATH.'
}

if (!(Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
if (!(Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $pythonExe -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
}

& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }

& .\.venv\Scripts\python.exe backend\repository.py
if ($LASTEXITCODE -ne 0) {
    throw 'SQL Server initialization failed. Check SQLSERVER_CONNECTION_STRING in .env.'
}

& npm.cmd ci --ignore-scripts
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }

Write-Host 'Setup complete. Run .\start-local.ps1'

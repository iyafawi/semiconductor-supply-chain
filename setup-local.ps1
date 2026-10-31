param([switch]$InstallSqlServer)
$ErrorActionPreference='Stop'
$taskProject=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $taskProject
if($InstallSqlServer){
  winget install --id Microsoft.SQLServer.2025.Express --exact --source winget --silent --accept-package-agreements --accept-source-agreements
  if($LASTEXITCODE -ne 0){throw 'SQL Server installation failed or requires Windows elevation. Install Express and retry.'}
  winget install --id Microsoft.msodbcsql.18 --exact --source winget --silent --accept-package-agreements --accept-source-agreements
}
if(!(Test-Path '.env')){Copy-Item -LiteralPath '.env.example' -Destination '.env'}
$taskPython=$env:SILICONWATCH_PYTHON
if(!$taskPython){
  $taskBundled=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
  if(Test-Path -LiteralPath $taskBundled){$taskPython=$taskBundled}else{$taskPython='python'}
}
if(!(Test-Path '.venv\Scripts\python.exe')){& $taskPython -m venv .venv;if($LASTEXITCODE -ne 0){throw 'Install Python 3.11+ or set SILICONWATCH_PYTHON.'}}
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if($LASTEXITCODE -ne 0){throw 'Python dependency installation failed'}
& .\.venv\Scripts\python.exe backend\repository.py
if($LASTEXITCODE -ne 0){throw 'SQL Server connection or initialization failed. Set SQLSERVER_CONNECTION_STRING in .env.'}
$taskNode=$env:SILICONWATCH_NODE
if(!$taskNode){$taskNode=(Get-Command node -ErrorAction SilentlyContinue).Source}
if(!$taskNode){$taskNode=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'}
if(!(Test-Path 'node_modules\vite\bin\vite.js')){
  $taskNpm=Get-Command npm -ErrorAction SilentlyContinue
  if($taskNpm){npm install}else{
    $taskPnpm=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\pnpm\bin\pnpm.cjs'
    if(!(Test-Path -LiteralPath $taskPnpm)){throw 'Install Node.js 22+ with npm first.'}
    & $taskNode $taskPnpm install
  }
  if($LASTEXITCODE -ne 0){throw 'Frontend dependency installation failed'}
}
# Vite reads VITE_API_URL from .env; Python reads only its backend settings.
& $taskNode node_modules\vite\bin\vite.js build
if($LASTEXITCODE -ne 0){throw 'Frontend build failed'}
Write-Host 'Local system ready. Run .\start-local.ps1'

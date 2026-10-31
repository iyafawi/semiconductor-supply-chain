param([switch]$NoBrowser)
$ErrorActionPreference='Stop'
$taskProject=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $taskProject
$taskPython=Join-Path $taskProject '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $taskPython)) { throw 'Run setup-local.ps1 first to install prerequisites and initialize SQL Server.' }
if (!(Test-Path -LiteralPath '.env')) { throw 'Copy .env.example to .env and set the local SQL Server connection.' }
if (!(Test-Path -LiteralPath 'dist\index.html')) { throw 'Run setup-local.ps1 to build the frontend.' }
$taskState=Join-Path $taskProject '.local-runtime'
New-Item -ItemType Directory -Path $taskState -Force | Out-Null
$taskRecord=Join-Path $taskState 'processes.json'
if (Test-Path -LiteralPath $taskRecord) {
  $taskOld=Get-Content -LiteralPath $taskRecord -Raw | ConvertFrom-Json
  foreach($taskEntry in $taskOld) {
    $taskRunning=Get-Process -Id $taskEntry.pid -ErrorAction SilentlyContinue
    if($taskRunning -and $taskRunning.StartTime.ToUniversalTime().ToString('o') -eq $taskEntry.started_at) { throw 'Services already running. Use stop-local.ps1 before restarting.' }
  }
}
# Connect and migrate before opening services. Failure is explicit; no JSON/SQLite fallback.
& $taskPython backend\repository.py
if($LASTEXITCODE -ne 0) { throw 'SQL Server initialization failed.' }
$taskCommands=@(
  @{name='api';args=@('-m','uvicorn','main:app','--app-dir','backend','--host','127.0.0.1','--port','8000')},
  @{name='worker';args=@('backend\worker.py')},
  @{name='frontend';args=@('backend\serve_frontend.py')}
)
$taskProcesses=@()
try {
  foreach($taskCommand in $taskCommands) {
    $taskProcess=Start-Process -FilePath $taskPython -ArgumentList $taskCommand.args -WorkingDirectory $taskProject -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskState ($taskCommand.name+'.out.log')) -RedirectStandardError (Join-Path $taskState ($taskCommand.name+'.error.log'))
    $taskProcesses+=@{name=$taskCommand.name;pid=$taskProcess.Id;started_at=$taskProcess.StartTime.ToUniversalTime().ToString('o')}
  }
  $taskProcesses | ConvertTo-Json | Set-Content -LiteralPath $taskRecord
  $taskReady=$false
  for($taskAttempt=0;$taskAttempt -lt 20;$taskAttempt++) {
    try { $null=Invoke-RestMethod 'http://127.0.0.1:8000/api/health';$taskReady=$true;break } catch { Start-Sleep -Milliseconds 500 }
  }
  if(!$taskReady) { throw 'API did not become ready. Check .local-runtime logs.' }
  Write-Host 'Private local dashboard: http://127.0.0.1:5173'
  Write-Host 'FastAPI documentation: http://127.0.0.1:8000/docs'
  Write-Host 'Worker refreshes every 10 minutes; dashboard every 45 seconds. Logs: .local-runtime/'
  Write-Host 'Stop application services with .\stop-local.ps1. SQL Server remains installed as a local service.'
  if(!$NoBrowser){Start-Process 'http://127.0.0.1:5173'}
} catch {
  foreach($taskEntry in $taskProcesses) { Stop-Process -Id $taskEntry.pid -ErrorAction SilentlyContinue }
  throw
}

$ErrorActionPreference='Stop'
$taskProject=Split-Path -Parent $MyInvocation.MyCommand.Path
$taskRecord=Join-Path $taskProject '.local-runtime\processes.json'
if(!(Test-Path -LiteralPath $taskRecord)){Write-Host 'No managed application processes found.';exit}
$taskEntries=Get-Content -LiteralPath $taskRecord -Raw | ConvertFrom-Json
foreach($taskEntry in $taskEntries){
  $taskProcess=Get-Process -Id $taskEntry.pid -ErrorAction SilentlyContinue
  if($taskProcess -and $taskProcess.StartTime.ToUniversalTime().ToString('o') -eq $taskEntry.started_at){Stop-Process -Id $taskEntry.pid;Write-Host ('Stopped '+$taskEntry.name)}
}
Remove-Item -LiteralPath $taskRecord

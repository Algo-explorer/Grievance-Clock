$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
New-Item -ItemType Directory -Path (Join-Path $projectRoot 'tmp') -Force | Out-Null
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create the .venv and install backend dependencies first. See README.md.' }
$backendProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'tmp/backend.log' -RedirectStandardError 'tmp/backend-error.log'
$nodePath = (Get-Command node.exe).Source
$nextPath = Join-Path $projectRoot 'node_modules\next\dist\bin\next'
$frontendProcess = Start-Process -FilePath $nodePath -ArgumentList ('"' + $nextPath + '"'),'dev','--webpack','--hostname','127.0.0.1' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'tmp/frontend.log' -RedirectStandardError 'tmp/frontend-error.log'
@{ backend=$backendProcess.Id; frontend=$frontendProcess.Id; root=$projectRoot } | ConvertTo-Json | Set-Content -LiteralPath 'tmp/server-pids.json'
Write-Output 'Grievance Clock is starting at http://127.0.0.1:3000. Logs: tmp/'

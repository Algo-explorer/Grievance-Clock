$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pidFile = Join-Path $projectRoot 'tmp/server-pids.json'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Output 'No recorded server processes.'; exit }
$saved = Get-Content -LiteralPath $pidFile | ConvertFrom-Json
if ($saved.root -ne $projectRoot) { throw 'Recorded workspace does not match.' }
foreach ($processId in @($saved.backend,$saved.frontend)) {
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    if ($processInfo -and ($processInfo.CommandLine -like '*backend.main:app*' -or $processInfo.CommandLine -like ('*'+$projectRoot+'*next*'))) {
        Stop-Process -Id $processId
    }
}
Remove-Item -LiteralPath $pidFile
Write-Output 'Recorded servers stopped.'

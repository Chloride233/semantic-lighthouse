$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$pidFile = Join-Path $root ".runtime\v1-api.pid"

if (-not (Test-Path $pidFile)) {
    Write-Output "No PID file found."
    exit 0
}

$processId = [int](Get-Content -Raw -LiteralPath $pidFile)
$process = Get-Process -Id $processId -ErrorAction SilentlyContinue
if ($process -ne $null) {
    Stop-Process -Id $processId
    Write-Output "Stopped process $processId."
}
else {
    Write-Output "Process $processId is not running."
}

Remove-Item -LiteralPath $pidFile -Force

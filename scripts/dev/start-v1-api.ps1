param(
    [string]$DatabaseUrl = "sqlite+pysqlite:///./local_v1.db",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$runtimeDir = Join-Path $root ".runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Missing virtual environment Python at $python"
}

$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stdoutLog = Join-Path $logDir "v1-api.out.log"
$stderrLog = Join-Path $logDir "v1-api.err.log"

$env:DATABASE_URL = $DatabaseUrl
if ((Test-Path Env:Path) -and (Test-Path Env:PATH)) {
    Remove-Item Env:PATH
}
$process = Start-Process `
    -FilePath $python `
    -ArgumentList "-m uvicorn semantic_lighthouse.main:app --host 127.0.0.1 --port $Port" `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru
$pidFile = Join-Path $runtimeDir "v1-api.pid"
Set-Content -LiteralPath $pidFile -Value $process.Id

Write-Output "Started Semantic Lighthouse API on http://127.0.0.1:$Port"
Write-Output "PID: $($process.Id)"
Write-Output "PID file: $pidFile"
Write-Output "Stdout log: $stdoutLog"
Write-Output "Stderr log: $stderrLog"

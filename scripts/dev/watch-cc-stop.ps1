param(
    [string]$Path = ".tmp\cc-last-stop.json",
    [int]$PollSeconds = 2,
    [switch]$Once,
    [switch]$ShowGitStatus,
    [switch]$Bell
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$watchPath = Join-Path $repoRoot $Path
$lastWrite = $null
if (Test-Path $watchPath) {
    $lastWrite = (Get-Item $watchPath).LastWriteTimeUtc
}

Write-Host "Watching Claude Code stop signal: $watchPath"
Write-Host "Press Ctrl+C to stop."

while ($true) {
    Start-Sleep -Seconds $PollSeconds

    if (-not (Test-Path $watchPath)) {
        continue
    }

    $item = Get-Item $watchPath
    if ($null -ne $lastWrite -and $item.LastWriteTimeUtc -le $lastWrite) {
        continue
    }

    $lastWrite = $item.LastWriteTimeUtc
    $record = Get-Content -Raw -Path $watchPath | ConvertFrom-Json
    $completedAt = $record.completed_at
    $sessionId = $record.session_id

    Write-Host "::cc-stop-detected{path=`"$watchPath`" completed_at=`"$completedAt`" session_id=`"$sessionId`"}"

    if ($ShowGitStatus) {
        git status --short
    }

    if ($Bell) {
        [Console]::Beep(880, 180)
    }

    if ($Once) {
        break
    }
}

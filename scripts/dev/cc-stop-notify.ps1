param(
    [string]$OutPath = ".tmp\cc-last-stop.json"
)

$ErrorActionPreference = "Stop"

try {
    $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
    Set-Location $repoRoot

    $stdin = [Console]::In.ReadToEnd()
    $payload = $null
    if (-not [string]::IsNullOrWhiteSpace($stdin)) {
        try {
            $payload = $stdin | ConvertFrom-Json
        } catch {
            $payload = @{
                parse_error = $_.Exception.Message
                raw_input = $stdin
            }
        }
    }

    function Get-PayloadValue {
        param(
            [object]$Object,
            [string]$Name
        )

        if ($null -eq $Object) {
            return $null
        }
        if ($Object -is [hashtable] -and $Object.ContainsKey($Name)) {
            return $Object[$Name]
        }
        if ($Object.PSObject.Properties.Name -contains $Name) {
            return $Object.$Name
        }
        if ($Object -is [hashtable] -and $Object.ContainsKey("raw_input")) {
            $match = [regex]::Match(
                [string]$Object["raw_input"],
                '"' + [regex]::Escape($Name) + '"\s*:\s*"((?:\\.|[^"\\])*)"'
            )
            if ($match.Success) {
                return [regex]::Unescape($match.Groups[1].Value)
            }
        }
        return $null
    }

    $completedAt = (Get-Date).ToUniversalTime().ToString("o")
    $record = [ordered]@{
        status = "cc_stop"
        completed_at = $completedAt
        repo = $repoRoot.Path
        hook_event_name = Get-PayloadValue $payload "hook_event_name"
        session_id = Get-PayloadValue $payload "session_id"
        transcript_path = Get-PayloadValue $payload "transcript_path"
        raw_hook_input = $payload
    }

    $outFile = Join-Path $repoRoot $OutPath
    $outDir = Split-Path -Parent $outFile
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $record | ConvertTo-Json -Depth 20 | Set-Content -Path $outFile -Encoding UTF8

    Write-Host "::cc-stop{path=`"$outFile`" completed_at=`"$completedAt`"}"
    exit 0
} catch {
    Write-Warning "cc-stop-notify failed: $($_.Exception.Message)"
    exit 0
}

param(
  [int]$Port = 8000,
  [string]$HostAddress = "127.0.0.1",
  [switch]$SkipMigrations
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$url = "http://$HostAddress`:$Port/console"

function Set-EnvDefault {
  param(
    [string]$Name,
    [string]$Value
  )

  if (-not [Environment]::GetEnvironmentVariable($Name, "Process")) {
    [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
  }
}

function Import-PersistedEnv {
  param([string]$Name)

  if ([Environment]::GetEnvironmentVariable($Name, "Process")) {
    return
  }

  $userValue = [Environment]::GetEnvironmentVariable($Name, "User")
  if ($userValue) {
    [Environment]::SetEnvironmentVariable($Name, $userValue, "Process")
    return
  }

  $machineValue = [Environment]::GetEnvironmentVariable($Name, "Machine")
  if ($machineValue) {
    [Environment]::SetEnvironmentVariable($Name, $machineValue, "Process")
  }
}

if (-not (Test-Path $python)) {
  throw "Python venv not found: $python. Create the virtual environment before starting the app."
}

Set-Location $root
New-Item -ItemType Directory -Force -Path ".tmp" | Out-Null

Import-PersistedEnv "DEEPSEEK_API_KEY"
Import-PersistedEnv "DASHSCOPE_API_KEY"
Import-PersistedEnv "CHAT_PROVIDER"
Import-PersistedEnv "CHAT_MODEL"
Import-PersistedEnv "CHAT_BASE_URL"

Set-EnvDefault "DATABASE_URL" "sqlite+pysqlite:///F:/semantic-lighthouse/.tmp/frontend-preview.db"
Set-EnvDefault "JWT_SECRET_KEY" "local-preview-secret-key-at-least-32-bytes"
Set-EnvDefault "COOKIE_SECURE" "false"
Set-EnvDefault "CHAT_PROVIDER" "deepseek"
Set-EnvDefault "CHAT_MODEL" "deepseek-v4-flash"

$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existing) {
  Write-Host "Semantic Lighthouse already appears to be running on $url"
  Start-Process $url
  exit 0
}

if (-not [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "Process")) {
  Write-Warning "DEEPSEEK_API_KEY is not visible to this process. The app will start, but real DeepSeek answers will fail."
}

if (-not $SkipMigrations) {
  Write-Host "Running database migrations..."
  & $python -m alembic upgrade head
}

Write-Host "Starting Semantic Lighthouse on $url"
$command = "Set-Location -LiteralPath '$root'; & '$python' -m uvicorn semantic_lighthouse.main:app --host $HostAddress --port $Port"
Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $command) -WorkingDirectory $root

Start-Sleep -Seconds 2
Start-Process $url

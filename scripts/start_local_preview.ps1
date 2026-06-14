$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

New-Item -ItemType Directory -Force -Path ".tmp" | Out-Null
Remove-Item ".tmp\frontend-preview.log", ".tmp\frontend-preview.err" -ErrorAction SilentlyContinue

$env:DATABASE_URL = "sqlite+pysqlite:///F:/semantic-lighthouse/.tmp/frontend-preview.db"
$env:JWT_SECRET_KEY = "local-preview-secret-key-at-least-32-bytes"
$env:EMBEDDING_PROVIDER = "fake"
$env:EMBEDDING_MODEL = "fake"
$env:EMBEDDING_DIMENSION = "8"
$env:CHAT_PROVIDER = "fake"
$env:CHAT_MODEL = "fake"
$env:COOKIE_SECURE = "false"

Start-Process `
  -FilePath ".\.venv\Scripts\python.exe" `
  -ArgumentList @("-m", "uvicorn", "semantic_lighthouse.main:app", "--host", "127.0.0.1", "--port", "8000") `
  -WorkingDirectory $root `
  -RedirectStandardOutput "$root\.tmp\frontend-preview.log" `
  -RedirectStandardError "$root\.tmp\frontend-preview.err" `
  -WindowStyle Hidden `
  -PassThru |
  Select-Object Id, ProcessName

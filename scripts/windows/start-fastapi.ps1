param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8001
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
& (Join-Path $PSScriptRoot 'verify-ml-artifacts.ps1')
& (Join-Path $PSScriptRoot 'verify-firebase-admin.ps1')
Set-Location (Join-Path $repoRoot 'packages\backend')
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port $Port

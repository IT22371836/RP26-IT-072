$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
& (Join-Path $PSScriptRoot 'verify-ml-artifacts.ps1')
& (Join-Path $PSScriptRoot 'verify-firebase-admin.ps1')
Set-Location (Join-Path $repoRoot 'packages\backend')
& '.\.venv\Scripts\python.exe' -m app.pipeline.worker

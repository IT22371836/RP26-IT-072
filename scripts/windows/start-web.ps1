param(
    [string]$ApiBaseUrl = ''
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if ($ApiBaseUrl) {
    $env:VITE_API_BASE_URL = $ApiBaseUrl
}
Set-Location (Join-Path $repoRoot 'WEB')
& npm.cmd run dev

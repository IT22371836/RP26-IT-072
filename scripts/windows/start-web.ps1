param(
    [string]$ApiBaseUrl = '',
    [string]$ListenHost = '127.0.0.1'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if ($ApiBaseUrl) {
    $env:VITE_API_BASE_URL = $ApiBaseUrl
}
Set-Location (Join-Path $repoRoot 'WEB')
& npm.cmd run dev -- --host $ListenHost

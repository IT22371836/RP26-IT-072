$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$backendRoot = Join-Path $repoRoot 'packages\backend'
$credentialSetting = [Environment]::GetEnvironmentVariable(
  'FIREBASE_CREDENTIALS_PATH',
  'Process'
)

if ([string]::IsNullOrWhiteSpace($credentialSetting)) {
  $envFile = Join-Path $backendRoot '.env'
  if (Test-Path -LiteralPath $envFile) {
    $entry = Get-Content -LiteralPath $envFile | Where-Object {
      $_ -match '^\s*FIREBASE_CREDENTIALS_PATH\s*='
    } | Select-Object -Last 1
    if ($entry) {
      $credentialSetting = ($entry -split '=', 2)[1].Trim().Trim('"').Trim("'")
    }
  }
}

if ([string]::IsNullOrWhiteSpace($credentialSetting)) {
  Write-Warning 'FIREBASE_CREDENTIALS_PATH is empty; Application Default Credentials must be available.'
  return
}

$credentialPath = $credentialSetting
if (-not [System.IO.Path]::IsPathRooted($credentialPath)) {
  $credentialPath = [System.IO.Path]::GetFullPath(
    (Join-Path $backendRoot $credentialPath)
  )
}

if (-not (Test-Path -LiteralPath $credentialPath -PathType Leaf)) {
  throw "Missing Firebase Admin credential file: $credentialPath"
}

Write-Output 'Firebase Admin credential file: ready'

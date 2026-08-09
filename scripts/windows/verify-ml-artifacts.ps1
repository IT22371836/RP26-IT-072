$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$required = @(
  'packages\backend\app\components\component1\artifacts\providers.json',
  'packages\backend\app\components\component1\artifacts\provider_embeddings.npy',
  'ml\components\component4\data\processed\provider_id_map.csv',
  'ml\components\component4\artifacts\catf-v1\provider_catf_scores.csv'
)

foreach ($relativePath in $required) {
  $path = Join-Path $repoRoot $relativePath
  if (-not (Test-Path -LiteralPath $path)) { throw "Missing ML artifact: $relativePath" }
  $stream = [System.IO.File]::OpenRead($path)
  try {
    $buffer = New-Object byte[] 80
    $read = $stream.Read($buffer, 0, $buffer.Length)
    $prefix = [System.Text.Encoding]::ASCII.GetString($buffer, 0, $read)
  } finally {
    $stream.Dispose()
  }
  if ($prefix.StartsWith('version https://git-lfs.github.com/spec/v1')) {
    throw "ML artifact is still a Git LFS pointer: $relativePath. Run git lfs pull."
  }
  $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower()
  Write-Output "$relativePath $hash"
}

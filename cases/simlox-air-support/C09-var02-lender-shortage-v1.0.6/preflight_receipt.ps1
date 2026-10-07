function Get-SourceMapSha([object]$map) {
  $json = ConvertTo-Json -InputObject $map -Compress -Depth 10
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
  $hasher = [System.Security.Cryptography.SHA256]::Create()
  try { return ([BitConverter]::ToString($hasher.ComputeHash($bytes))).Replace('-','').ToLowerInvariant() }
  finally { $hasher.Dispose() }
}

function Assert-JsonInteger([object]$value,[long]$expected,[string]$field) {
  if (-not ($value -is [int] -or $value -is [long]) -or $value -ne $expected) {
    throw "approved preflight $field has wrong JSON integer type/value"
  }
}
function Assert-JsonBoolean([object]$value,[bool]$expected,[string]$field) {
  if (-not ($value -is [bool]) -or $value -ne $expected) {
    throw "approved preflight $field has wrong JSON boolean type/value"
  }
}

function Assert-PreflightReceiptData([object]$receipt,[string]$runId,[string]$manifestSha,[object]$sourceMap) {
  if ($receipt.schema -ne 'c09-var02-v106-ssh-preflight/v1' -or $receipt.run_id -ne $runId -or
      $receipt.manifest_sha256 -ne $manifestSha -or $receipt.source_map_sha256 -ne (Get-SourceMapSha $sourceMap)) {
    throw 'approved preflight schema/run/manifest/source-map differs'
  }
  Assert-JsonInteger $receipt.ssh_session 0 'ssh_session'
  Assert-JsonInteger $receipt.ps_major 5 'ps_major'
  Assert-JsonInteger $receipt.wts_active_gui_count 1 'wts_active_gui_count'
  Assert-JsonInteger $receipt.gui.pid 13340 'gui.pid'
  Assert-JsonInteger $receipt.gui.session_id 1 'gui.session_id'
  Assert-JsonInteger $receipt.gui.start_unix_ms 1790590196826 'gui.start_unix_ms'
  Assert-JsonBoolean $receipt.mutex_free $true 'mutex_free'
  Assert-JsonBoolean $receipt.run_dirs_absent $true 'run_dirs_absent'
  Assert-JsonBoolean $receipt.native_process_started $false 'native_process_started'
  Assert-JsonBoolean $receipt.gui.responding $true 'gui.responding'
  if (-not ($receipt.ssh_ancestors -is [array]) -or @($receipt.ssh_ancestors) -notcontains 'sshd.exe') {
    throw 'approved preflight sshd ancestry differs'
  }
  $actualKeys = @($receipt.source_hashes.PSObject.Properties.Name | Sort-Object)
  $expectedKeys = @($sourceMap.Keys | Sort-Object)
  if (($actualKeys -join '|') -ne ($expectedKeys -join '|')) { throw 'approved preflight source-map keys differ' }
  foreach ($key in $expectedKeys) {
    if ($receipt.source_hashes.$key -ne $sourceMap[$key]) { throw "approved preflight source differs: $key" }
  }
  Assert-JsonInteger $receipt.accepted_raw_seals 130 'accepted_raw_seals'
  Assert-JsonInteger $receipt.accepted_closures 10 'accepted_closures'
  Assert-JsonInteger $receipt.accepted_invocations 10 'accepted_invocations'
  return $true
}

function Assert-PreflightReceiptPath([string]$case,[string]$relative,[string]$expectedSha,
                                     [string]$runId,[string]$manifestSha,[object]$sourceMap) {
  if ([System.IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[\\/])\.\.([\\/]|$)' -or
      $relative -notmatch '^review[\\/]preflight-ssh0-[0-9]{8}T[0-9]{9}Z\.json$') {
    throw 'approved preflight path is not a direct owned review receipt'
  }
  $reviewRoot = [System.IO.Path]::GetFullPath((Join-Path $case 'review'))
  $path = [System.IO.Path]::GetFullPath((Join-Path $case $relative))
  if (-not $path.StartsWith($reviewRoot + [System.IO.Path]::DirectorySeparatorChar,
                            [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'approved preflight resolves outside owned review directory'
  }
  $cursor = [System.IO.Path]::GetPathRoot($path)
  foreach ($part in $path.Substring($cursor.Length).Split([System.IO.Path]::DirectorySeparatorChar)) {
    if ($part -eq '') { continue }
    $cursor = Join-Path $cursor $part
    if (Test-Path -LiteralPath $cursor) {
      $entry = Get-Item -LiteralPath $cursor -Force
      if (($entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'approved preflight path traverses a reparse point'
      }
    }
  }
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'approved preflight receipt missing' }
  if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedSha) {
    throw 'approved preflight receipt SHA differs'
  }
  $receipt = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
  [void](Assert-PreflightReceiptData $receipt $runId $manifestSha $sourceMap)
  return $path
}

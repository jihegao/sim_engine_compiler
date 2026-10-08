function Get-SourceMapSha([object]$map) {
  $json = ConvertTo-Json -InputObject $map -Compress -Depth 10
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
  $hasher = [System.Security.Cryptography.SHA256]::Create()
  try { return ([BitConverter]::ToString($hasher.ComputeHash($bytes))).Replace('-','').ToLowerInvariant() }
  finally { $hasher.Dispose() }
}

function Get-ReceiptFileSha([string]$path) {
  $stream = [System.IO.File]::OpenRead($path)
  $hasher = [System.Security.Cryptography.SHA256]::Create()
  try { return ([BitConverter]::ToString($hasher.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
  finally { $stream.Dispose(); $hasher.Dispose() }
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
function Assert-JsonKeys([object]$value,[string[]]$expected,[string]$field) {
  if ($null -eq $value -or $value -is [array]) { throw "$field is not a JSON object" }
  $actual=@($value.PSObject.Properties.Name | Sort-Object)
  $wanted=@($expected | Sort-Object)
  if (($actual -join '|') -cne ($wanted -join '|')) { throw "$field key set differs" }
}
function Assert-RunDirectory([object]$value,[string]$expected,[string]$field) {
  if (-not ($value -is [string]) -or $value -cne $expected) {
    throw "$field is not the exact approved native run directory string"
  }
}

function Assert-PreflightReceiptData([object]$receipt,[string]$case,[string]$runId,[string]$nativeRunDir,[string]$manifestSha,[object]$sourceMap) {
  Assert-JsonKeys $receipt @('schema','run_id','native_run_directory','run_dirs_absent',
    'file_line_ascii_bytes','file_line_ascii_max','native_run_path_ancestors_no_reparse',
    'ssh_session','ps_major','ssh_ancestors','mutex_free','wts_active_gui_count','gui',
    'accepted_source_pair_count','required_local_source_count','mandatory_original_count',
    'archived_catalog_count','converter_negative_original_count','installed_executable_count',
    'catalog_prefix_entries',
    'manifest_sha256','source_map_sha256','source_hashes',
    'source_hashes_after_pure','pure_proof_directory','pure_proof_path','pure_proof_sha256',
    'pure_checks','native_process_started') 'approved preflight'
  Assert-RunDirectory $receipt.native_run_directory $nativeRunDir 'approved preflight native_run_directory'
  if ($receipt.schema -ne 'a17-var06-ssh-preflight/v100' -or $receipt.run_id -ne $runId -or
      $receipt.manifest_sha256 -ne $manifestSha -or $receipt.source_map_sha256 -ne (Get-SourceMapSha $sourceMap)) {
    throw 'approved preflight schema/run/manifest/source-map differs'
  }
  Assert-JsonKeys $receipt.gui @('pid','session_id','start_unix_ms','responding') 'approved preflight GUI'
  Assert-JsonInteger $receipt.ssh_session 0 'ssh_session'
  Assert-JsonInteger $receipt.ps_major 5 'ps_major'
  Assert-JsonInteger $receipt.wts_active_gui_count 1 'wts_active_gui_count'
  Assert-JsonInteger $receipt.gui.pid 13340 'gui.pid'
  Assert-JsonInteger $receipt.gui.session_id 1 'gui.session_id'
  Assert-JsonInteger $receipt.gui.start_unix_ms 1790590196826 'gui.start_unix_ms'
  Assert-JsonBoolean $receipt.mutex_free $true 'mutex_free'
  Assert-JsonBoolean $receipt.run_dirs_absent $true 'run_dirs_absent'
  Assert-JsonInteger $receipt.file_line_ascii_bytes 182 'file_line_ascii_bytes'
  Assert-JsonInteger $receipt.file_line_ascii_max 199 'file_line_ascii_max'
  Assert-JsonBoolean $receipt.native_run_path_ancestors_no_reparse $true 'native_run_path_ancestors_no_reparse'
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
  Assert-JsonInteger $receipt.accepted_source_pair_count 59 'accepted_source_pair_count'
  Assert-JsonInteger $receipt.required_local_source_count 12 'required_local_source_count'
  Assert-JsonInteger $receipt.mandatory_original_count 66 'mandatory_original_count'
  Assert-JsonInteger $receipt.archived_catalog_count 2 'archived_catalog_count'
  Assert-JsonInteger $receipt.converter_negative_original_count 1 'converter_negative_original_count'
  Assert-JsonInteger $receipt.installed_executable_count 2 'installed_executable_count'
  Assert-JsonInteger $receipt.catalog_prefix_entries 502 'catalog_prefix_entries'
  $expectedTools=@('build.py','source_gate.py','self_check.py','make_source_inventory.py','make_prelaunch_manifest.py')
  if (@($receipt.pure_checks).Count -ne $expectedTools.Count -or
      -not $receipt.pure_proof_directory -or
      -not (Test-Path -LiteralPath $receipt.pure_proof_directory -PathType Container)) {
    throw 'approved preflight pure proof missing'
  }
  $testRoot=[System.IO.Path]::GetFullPath((Join-Path $case 'test-output'))
  if (-not [System.IO.Path]::GetFullPath($receipt.pure_proof_directory).StartsWith(
      $testRoot + [System.IO.Path]::DirectorySeparatorChar,[System.StringComparison]::OrdinalIgnoreCase) -or
      [System.IO.Path]::GetFileName($receipt.pure_proof_directory) -notmatch '^preflight-pure-[0-9]{8}T[0-9]{13}Z-[0-9a-f]{8}$') {
    throw 'approved preflight pure directory differs'
  }
  $proofPath=Join-Path $receipt.pure_proof_directory 'pure-proof.json'
  if ($receipt.pure_proof_path -ne $proofPath -or
      -not (Test-Path -LiteralPath $proofPath -PathType Leaf) -or
      (Get-ReceiptFileSha $proofPath) -ne $receipt.pure_proof_sha256) {
    throw 'approved preflight pure proof receipt drift'
  }
  $proof=Get-Content -LiteralPath $proofPath -Raw -Encoding UTF8 | ConvertFrom-Json
  Assert-JsonKeys $proof @('schema','mode','run_id','native_run_directory','manifest_sha256',
    'source_map_sha256','started_utc','completed_utc','status','error','checks',
    'source_hashes_after') 'approved preflight pure proof'
  Assert-RunDirectory $proof.native_run_directory $nativeRunDir 'approved pure proof native_run_directory'
  if ($proof.schema -ne 'a17-var06-pure-proof/v100' -or $proof.mode -ne 'preflight' -or
      $proof.status -ne 'passed' -or $proof.run_id -ne $runId -or
      $null -ne $proof.error -or
      $proof.manifest_sha256 -ne $manifestSha -or
      $proof.source_map_sha256 -ne (Get-SourceMapSha $sourceMap) -or
      @($proof.checks).Count -ne $expectedTools.Count) {
    throw 'approved preflight pure proof identity differs'
  }
  $afterKeys=@($receipt.source_hashes_after_pure.PSObject.Properties.Name | Sort-Object)
  $proofAfterKeys=@($proof.source_hashes_after.PSObject.Properties.Name | Sort-Object)
  if (($afterKeys -join '|') -ne ($expectedKeys -join '|') -or
      ($proofAfterKeys -join '|') -ne ($expectedKeys -join '|')) {
    throw 'approved preflight after-pure source-map keys differ'
  }
  foreach ($key in $expectedKeys) {
    if ($receipt.source_hashes_after_pure.$key -ne $sourceMap[$key] -or
        $proof.source_hashes_after.$key -ne $sourceMap[$key]) {
      throw "approved preflight after-pure source drift: $key"
    }
  }
  $previousCompleted=[DateTimeOffset]::Parse($proof.started_utc)
  for ($i=0; $i -lt $expectedTools.Count; $i++) {
    $step=$receipt.pure_checks[$i]
    $record=$proof.checks[$i]
    $stepKeys=@('tool','program','arguments','started_utc','completed_utc','status','error',
      'child_pid','child_session_id','exit_code','capture_error','stdout_path','stderr_path',
      'stdout_bytes','stderr_bytes','stdout_sha256','stderr_sha256')
    Assert-JsonKeys $step $stepKeys "approved preflight pure helper[$i]"
    Assert-JsonKeys $record $stepKeys "approved proof pure helper[$i]"
    if ((ConvertTo-Json -InputObject $step -Compress -Depth 10) -cne
        (ConvertTo-Json -InputObject $record -Compress -Depth 10)) {
      throw 'approved preflight pure check/proof record differs'
    }
    $expectedArgs='-X utf8 -B "' + (Join-Path $case $expectedTools[$i]) + '"'
    if ($step.tool -cne $expectedTools[$i] -or $step.status -ne 'completed' -or
        $step.error -ne $null -or $step.capture_error -ne $null -or
        $step.program -ne 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -or
        $step.arguments -cne $expectedArgs) {
      throw 'approved preflight pure helper identity/capture differs'
    }
    $started=[DateTimeOffset]::Parse($step.started_utc)
    $completed=[DateTimeOffset]::Parse($step.completed_utc)
    if ($started -lt $previousCompleted -or $completed -lt $started) {
      throw 'approved preflight pure helper UTC sequence differs'
    }
    $previousCompleted=$completed
    Assert-JsonInteger $step.exit_code 0 "pure_checks[$i].exit_code"
    Assert-JsonInteger $step.child_session_id 0 "pure_checks[$i].child_session_id"
    if (-not ($step.child_pid -is [int] -or $step.child_pid -is [long]) -or $step.child_pid -le 0) {
      throw 'approved preflight helper PID invalid'
    }
    foreach ($stream in @('stdout','stderr')) {
      $path=$step.($stream + '_path')
      $length=$step.($stream + '_bytes')
      $hash=$step.($stream + '_sha256')
      $expectedPath=Join-Path $receipt.pure_proof_directory ([System.IO.Path]::GetFileNameWithoutExtension($expectedTools[$i]) + '-' + $stream + '.bin')
      if ($path -cne $expectedPath -or -not [System.IO.Path]::GetFullPath($path).StartsWith(
          [System.IO.Path]::GetFullPath($receipt.pure_proof_directory) + [System.IO.Path]::DirectorySeparatorChar,
          [System.StringComparison]::OrdinalIgnoreCase) -or
          -not (Test-Path -LiteralPath $path -PathType Leaf) -or
          (Get-Item -LiteralPath $path).Length -ne $length -or (Get-ReceiptFileSha $path) -ne $hash) {
        throw 'approved preflight pure helper original stream drift'
      }
    }
    Assert-JsonInteger $step.stderr_bytes 0 "pure_checks[$i].stderr_bytes"
  }
  if ([DateTimeOffset]::Parse($proof.completed_utc) -lt $previousCompleted) {
    throw 'approved preflight proof completion precedes helpers'
  }
  return $true
}

function Assert-PreflightReceiptPath([string]$case,[string]$relative,[string]$expectedSha,
                                     [string]$runId,[string]$nativeRunDir,[string]$manifestSha,[object]$sourceMap) {
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
  if ((Get-ReceiptFileSha $path) -ne $expectedSha) {
    throw 'approved preflight receipt SHA differs'
  }
  $receipt = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
  [void](Assert-PreflightReceiptData $receipt $case $runId $nativeRunDir $manifestSha $sourceMap)
  return $path
}

param([switch]$PreflightOnly)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$manifestPath = Join-Path $case 'prelaunch-manifest.json'
$approvalPath = Join-Path $case 'review\independent-prelaunch-go.json'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo'
$runId = 'i05-var07-turnround-v101-ssh-20261009-01'
$nativeRunDirectory = 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\tmp\i05-var07-native-v101-20261009-01'
. (Join-Path $case 'captured_process.ps1')
. (Join-Path $case 'preflight_receipt.ps1')
. (Join-Path $case 'checker_receipt.ps1')

function Get-Sha([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Observed-Sha([string]$path) {
  if (Test-Path -LiteralPath $path -PathType Leaf) { return Get-Sha $path }
  return $null
}
function Assert-NoReparseSourcePath([string]$path) {
  if (-not [System.IO.Path]::IsPathRooted($path) -or
      [System.IO.Path]::GetFullPath($path) -cne $path) { throw 'source path not canonical absolute' }
  $cursor=[System.IO.Path]::GetPathRoot($path)
  foreach ($part in $path.Substring($cursor.Length).Split([System.IO.Path]::DirectorySeparatorChar)) {
    if ($part -eq '') { continue }
    $cursor=Join-Path $cursor $part
    $item=Get-Item -LiteralPath $cursor -Force -ErrorAction SilentlyContinue
    if ($item -and (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
      throw "source traverses reparse point: $path"
    }
  }
}
function Source-Hashes {
  $result = [ordered]@{}
  foreach ($entry in $manifest.source_files) {
    Assert-NoReparseSourcePath $entry.path
    if (-not (Test-Path -LiteralPath $entry.path -PathType Leaf)) { throw "source absent: $($entry.key)" }
    $file = Get-Item -LiteralPath $entry.path
    $hash = Get-Sha $entry.path
    if ($hash -ne $entry.sha256 -or $file.Length -ne $entry.bytes) { throw "source changed: $($entry.key)" }
    if ([int]$file.Attributes -ne [int]$entry.attributes -or
        $file.IsReadOnly -ne [bool]([int]$entry.attributes -band 1)) {
      throw "source mode/attributes changed: $($entry.key)"
    }
    $observedMode=if ($file.Extension -ieq '.exe') { 511 }
                  elseif ($file.IsReadOnly) { 292 } else { 438 }
    if ($observedMode -ne [int]$entry.mode) {
      throw "source Windows file mode changed: $($entry.key)"
    }
    if ($entry.key -clike 'owned:*' -and -not $file.IsReadOnly) {
      throw "owned source is writable: $($entry.key)"
    }
    $result[$entry.key] = $hash
  }
  if ($result.Count -ne $manifest.source_count) { throw 'source role count differs' }
  return $result
}
function Assert-Source-Stable {
  $current=Source-Hashes
  if (($current.Keys -join '|') -cne ($script:before.Keys -join '|')) { throw 'source-map keys changed' }
  foreach ($key in $script:before.Keys) {
    if ($current[$key] -ne $script:before[$key]) { throw "source changed: $key" }
  }
}
function Observed-Hashes {
  $result = [ordered]@{}
  foreach ($entry in $manifest.source_files) {
    if (Test-Path -LiteralPath $entry.path -PathType Leaf) { $result[$entry.key] = Get-Sha $entry.path }
    else { $result[$entry.key] = $null }
  }
  return $result
}
function Assert-Gui {
  $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne 1 -or
      -not $p[0].Responding -or
      ([DateTimeOffset]$p[0].StartTime.ToUniversalTime()).ToUnixTimeMilliseconds() -ne 1790590196826) {
    throw 'protected GUI PID/session/start/responding changed'
  }
}
function Assert-CompetingRunner {
  $native = @(Get-CimInstance Win32_Process -Filter "Name='Simlox.exe'" | Where-Object { $_.ProcessId -ne 13340 })
  if ($native.Count -ne 0) { throw 'another SIMLOX native child is active' }
  $runners = @(Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and $script:ancestorIds -notcontains $_.ProcessId -and
    $_.Name -match '^(powershell|pwsh|python|pythonw|cmd)\.exe$' -and
    $_.CommandLine -match '(?i)(run_native|invoke_loopback|(?:run|invoke|probe)[^\s]*_ssh)'
  })
  if ($runners.Count -ne 0) { throw 'competing native runner present' }
}
function Assert-Wts {
  $sessions=@(qwinsta 2>&1)
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {
    $_ -match '^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+1\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)'
  }).Count -ne 1) { throw 'protected GUI WTS session not active' }
}
function Assert-Guard {
  if ((Get-Sha $manifestPath) -cne $script:manifestShaAtLaunch) {
    throw 'prelaunch manifest changed during guarded execution'
  }
  $catalog=$manifest.live_catalog_prelaunch_pin
  if (-not $catalog -or -not (Test-Path -LiteralPath $catalog.path -PathType Leaf) -or
      (Get-Item -LiteralPath $catalog.path).Length -ne $catalog.bytes -or
      (Get-Sha $catalog.path) -ne $catalog.sha256) { throw 'live prelaunch catalog bytes changed' }
  Assert-Gui
  Assert-Wts
  Assert-CompetingRunner
  Assert-NativeRunPath
}
function Assert-NativeRunPath {
  if (-not [System.IO.Path]::IsPathRooted($nativeRunDirectory) -or
      [System.IO.Path]::GetFullPath($nativeRunDirectory) -cne $nativeRunDirectory -or
      $manifest.native_run_directory -cne $nativeRunDirectory) { throw 'native run directory identity differs' }
  $fileLine='File: ' + (Join-Path $nativeRunDirectory 'model.sxi').Replace('\','/')
  $inputLine='Input file: '+(Join-Path $nativeRunDirectory 'model.sxi')
  $outputLine='Output file: '+(Join-Path $nativeRunDirectory 'model.sxo')
  if ($inputLine -cne [System.Text.Encoding]::ASCII.GetString([System.Text.Encoding]::ASCII.GetBytes($inputLine)) -or
      $outputLine -cne [System.Text.Encoding]::ASCII.GetString([System.Text.Encoding]::ASCII.GetBytes($outputLine)) -or
      [System.Text.Encoding]::ASCII.GetByteCount($inputLine) -ne 125 -or
      [System.Text.Encoding]::ASCII.GetByteCount($outputLine) -ne 126) {
    throw 'native Input/Output path line spelling or ASCII length differs'
  }
  if (-not [System.Text.Encoding]::ASCII.GetString([System.Text.Encoding]::ASCII.GetBytes($fileLine)).Equals($fileLine) -or
      [System.Text.Encoding]::ASCII.GetByteCount($fileLine) -ne 119 -or
      [System.Text.Encoding]::ASCII.GetByteCount($fileLine) -gt 199) {
    throw 'native File line is non-ASCII or exceeds frozen bound'
  }
  $cursor=[System.IO.Path]::GetPathRoot($nativeRunDirectory)
  foreach ($part in $nativeRunDirectory.Substring($cursor.Length).Split([System.IO.Path]::DirectorySeparatorChar)) {
    if ($part -eq '') { continue }
    $cursor=Join-Path $cursor $part
    $entry=Get-Item -LiteralPath $cursor -Force -ErrorAction SilentlyContinue
    if ($entry) {
      if (($entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'native run path traverses a reparse point'
      }
    }
  }
}
function Assert-ConverterLog([string]$run,[string]$expectedSha) {
  $path=Join-Path $run 'model-run.log'
  if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Sha $path) -ne $expectedSha) {
    throw 'sealed converter log missing or changed'
  }
  $rawBytes=[System.IO.File]::ReadAllBytes($path)
  if ($rawBytes.Length -lt 2 -or
      ($rawBytes.Length -ge 3 -and $rawBytes[0] -eq 239 -and $rawBytes[1] -eq 187 -and $rawBytes[2] -eq 191) -or
      $rawBytes[$rawBytes.Length-2] -ne 13 -or $rawBytes[$rawBytes.Length-1] -ne 10) {
    throw 'converter BOM or terminal CRLF differs'
  }
  $text=[System.Text.UTF8Encoding]::new($false,$true).GetString($rawBytes)
  if ([regex]::Matches($text,"`n").Count -ne 17 -or
      [regex]::Matches($text,"`r`n").Count -ne 17) {
    throw 'converter exact 17 CRLF line endings differ'
  }
  foreach ($item in @(
    @('Input file','model.sxi'),@('Output file','model.sxo'),@('File','model.sxi')
  )) {
    $label=$item[0];$name=$item[1]
    $matches=[regex]::Matches($text,'(?m)^'+[regex]::Escape($label)+': ([^\r\n]+)\r?$')
    if ($matches.Count -ne 1) { throw "converter $label path cardinality differs" }
    $observed=$matches[0].Groups[1].Value
    $wanted=if ($label -eq 'File') { (Join-Path $run $name).Replace('\','/') }
            else { Join-Path $run $name }
    if ($observed -cne $wanted) { throw "converter $label path differs" }
    if ($label -eq 'File') {
      $line='File: '+$observed
      if ([System.Text.Encoding]::ASCII.GetString([System.Text.Encoding]::ASCII.GetBytes($line)) -cne $line) {
        throw 'converter File line is non-ASCII'
      }
      $lineBytes=[System.Text.Encoding]::ASCII.GetByteCount($line)
      if ($lineBytes -gt 199 -or ($run -ceq $nativeRunDirectory -and $lineBytes -ne 119)) {
        throw 'converter File line exceeds frozen ASCII length'
      }
    }
  }
  if ([regex]::Matches($text,'(?m)^Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0\r?$').Count -ne 1) {
    throw 'converter exact 0/2/0 summary differs'
  }
  $warnings=[regex]::Matches($text,'(?m)^Form: ([^\r\n]+)\r?\n(rec [^\r\n]+)\r?$')
  if ($warnings.Count -ne 2 -or $warnings[0].Groups[1].Value -cne 'Control' -or
      $warnings[0].Groups[2].Value -cne 'rec 1: (warning #108) Enabling simulation log may generate extensive data in log file' -or
      $warnings[1].Groups[1].Value -cne 'System' -or
      $warnings[1].Groups[2].Value -cne 'rec 1: (warning #126) This system contains no items: TEACH-AIR-01') {
    throw 'converter warning owner/text/order differs'
  }
  $codes=[regex]::Matches($text,'(?i)\b(warning|error|notice|note)\s*#(\d+)')
  if ($codes.Count -ne 2 -or $codes[0].Groups[1].Value.ToLowerInvariant() -ne 'warning' -or
      $codes[0].Groups[2].Value -ne '108' -or $codes[1].Groups[1].Value.ToLowerInvariant() -ne 'warning' -or
      $codes[1].Groups[2].Value -ne '126') { throw 'extra or altered converter diagnostic code' }
  if ([regex]::Matches($text,'(?m)^Form: ').Count -ne 2 -or
      [regex]::Matches($text,'(?m)^rec ').Count -ne 2) { throw 'extra converter Form or rec diagnostic' }
  $diagnosticLines=[regex]::Matches($text,'(?im)^[^\r\n]*\b(?:warnings?|errors?|notices?|notes?)\b[^\r\n]*\r?$')
  $allowed=@(
    'rec 1: (warning #108) Enabling simulation log may generate extensive data in log file',
    'rec 1: (warning #126) This system contains no items: TEACH-AIR-01',
    'Input conversion completed. Errors: 0, Warnings: 2, Notes: 0'
  )
  if ($diagnosticLines.Count -ne 3) { throw 'extra or missing converter diagnostic text' }
  foreach ($entry in $diagnosticLines) {
    if ($allowed -cnotcontains $entry.Value.TrimEnd("`r")) { throw 'unapproved converter diagnostic line' }
  }
  if ($text -match '(?<!\r)\n') { throw 'converter line endings differ from exact CRLF grammar' }
  $lines=@($text -split "`r`n")
  if ($lines.Count -eq 18 -and $lines[17] -ceq '') { $lines=@($lines[0..16]) }
  if ($lines.Count -ne 17) { throw 'converter line count differs from exact 17-line grammar' }
  $fixed=@(
    'Performing simulation',
    ('Input file: '+(Join-Path $run 'model.sxi')),
    ('Output file: '+(Join-Path $run 'model.sxo')),
    'Simulating.', 'Converting input data ...',
    ('File: '+(Join-Path $run 'model.sxi').Replace('\','/')),
    'Form: Control',
    'rec 1: (warning #108) Enabling simulation log may generate extensive data in log file',
    'Form: System',
    'rec 1: (warning #126) This system contains no items: TEACH-AIR-01',
    'Input conversion completed. Errors: 0, Warnings: 2, Notes: 0',
    $null, 'Starting simulation...', $null, 'Saving results ...', $null, $null
  )
  for ($i=0; $i -lt 17; $i++) {
    if ($null -ne $fixed[$i] -and $lines[$i] -cne $fixed[$i]) {
      throw "converter line $($i+1) differs from exact grammar"
    }
  }
  foreach ($item in @(@(11,'Input data conversion time'),@(13,'Simulation time'),
                     @(15,'Result saving time'),@(16,'Total execution time'))) {
    $index=[int]$item[0]; $label=[regex]::Escape([string]$item[1])
    $match=[regex]::Match($lines[$index],'^'+$label+': ([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?) secs\.$')
    if (-not $match.Success) { throw "converter timing line $($index+1) differs" }
    $seconds=0.0
    if (-not [double]::TryParse($match.Groups[1].Value,[System.Globalization.NumberStyles]::Float,
        [System.Globalization.CultureInfo]::InvariantCulture,[ref]$seconds) -or
        [double]::IsInfinity($seconds) -or [double]::IsNaN($seconds) -or $seconds -lt 0) {
      throw "converter timing line $($index+1) is not a finite nonnegative scalar"
    }
  }
}
function Save-Steps([string]$run) {
  ConvertTo-Json -InputObject $script:steps -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
}
function Run-Step([string]$run,[string]$name,[string]$program,[string]$arguments,
                  [string[]]$required,[bool]$checker) {
  $startedUtc=(Get-Date).ToUniversalTime()
  if ($script:steps.Count -gt 0) {
    $previous=$script:steps[$script:steps.Count-1]
    if ($previous.status -ne 'completed' -or -not $previous.completed_utc -or
        [DateTime]::Parse($previous.completed_utc).ToUniversalTime() -gt $startedUtc) {
      throw 'native/checker stage sequence or UTC ordering differs'
    }
  }
  $step = [ordered]@{sequence=$script:steps.Count;name=$name;program=$program;arguments=$arguments;
    started_utc=$startedUtc.ToString('o');
    completed_utc=$null;child_pid=$null;child_session_id=$null;exit_code=$null;capture_error=$null;
    stdout_path=$null;stderr_path=$null;stdout_bytes=$null;stderr_bytes=$null;
    stdout_sha256=$null;stderr_sha256=$null;converter_log_bytes=$null;converter_log_sha256=$null;
    converter_log_validated=$false;gui_preserved=$false;status='started';error=$null}
  $script:steps += $step
  try {
    Save-Steps $run
    Assert-Source-Stable
    Assert-Guard
    $stdoutName = if ($name -eq 'check_import_export') { 'roundtrip-validation.json' }
                  elseif ($name -eq 'check_behavior') { 'author-validation.json' }
                  else { $name + '-stdout.txt' }
    $stdout = Join-Path $run $stdoutName
    $stderr = Join-Path $run ($name + '-stderr.txt')
    $capture = Invoke-CapturedProcess $program $arguments $workingDirectory $stdout $stderr 0
    $step.child_pid = $capture.child_pid
    $step.child_session_id = $capture.child_session_id
    $step.exit_code = $capture.exit_code
    $step.capture_error = $capture.capture_error
    $step.stdout_path = $capture.stdout_path
    $step.stderr_path = $capture.stderr_path
    $step.stdout_bytes = $capture.stdout_bytes
    $step.stderr_bytes = $capture.stderr_bytes
    $step.stdout_sha256 = $capture.stdout_sha256
    $step.stderr_sha256 = $capture.stderr_sha256
    if ($name -eq 'calc') {
      $converterPath=Join-Path $run 'model-run.log'
      if (-not (Test-Path -LiteralPath $converterPath -PathType Leaf)) {
        throw 'calc converter log missing immediately after process capture'
      }
      $step.converter_log_bytes=(Get-Item -LiteralPath $converterPath).Length
      $step.converter_log_sha256=Get-Sha $converterPath
      (Get-Item -LiteralPath $converterPath).IsReadOnly=$true
    }
    Assert-Guard
    Assert-Source-Stable
    $step.gui_preserved = $true
    Assert-SuccessfulCapture $capture 0 | Out-Null
    foreach ($relative in $required) {
      $path = Join-Path $run $relative
      if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path).Length -le 4) {
        throw "$name output missing/empty: $relative"
      }
    }
    if ($checker) {
      $export = Get-Sha (Join-Path $run 'roundtrip-raw.json')
      Assert-CheckerVerdict $name $stdout $runId $nativeRunDirectory $before['owned:native-input.json'] $export | Out-Null
    }
    if ($name -eq 'calc' -and (Get-Sha (Join-Path $run 'model-run.log')) -cne $step.converter_log_sha256) {
      throw 'calc converter log changed after immediate seal'
    }
    $step.status = 'completed'
  } catch { $step.status='failed';$step.error=$_.Exception.Message;throw }
  finally {
    if ($name -eq 'calc') {
      $converterPath=Join-Path $run 'model-run.log'
      if (-not $step.converter_log_sha256 -and (Test-Path -LiteralPath $converterPath -PathType Leaf)) {
        $step.converter_log_bytes=(Get-Item -LiteralPath $converterPath).Length
        $step.converter_log_sha256=Get-Sha $converterPath
        (Get-Item -LiteralPath $converterPath).IsReadOnly=$true
      }
    }
    $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o');Save-Steps $run
  }
}
function Seal-Run([string]$run,[string]$errorText) {
  $stepError=$errorText
  $after = Observed-Hashes
  foreach ($key in $before.Keys) { if ($before[$key] -ne $after[$key]) { $errorText = "source drift: $key" } }
  $catalog=$manifest.live_catalog_prelaunch_pin
  if (-not (Test-Path -LiteralPath $catalog.path -PathType Leaf) -or
      (Get-Item -LiteralPath $catalog.path).Length -ne $catalog.bytes -or
      (Get-Sha $catalog.path) -ne $catalog.sha256) { $errorText = 'live prelaunch catalog bytes changed' }
  $manifestAfter = Observed-Sha $manifestPath
  $approvalAfter = Observed-Sha $approvalPath
  $preflightAfter = Observed-Sha $script:preflightPath
  if ($manifestAfter -ne $approval.manifest_sha256 -or $approvalAfter -ne $script:approvalSha -or
      $preflightAfter -ne $approval.preflight_sha256) { $errorText = 'authorization file drift' }
  if ((Observed-Sha (Join-Path $case 'review\independent_reader.py')) -ne $approval.independent_reader_sha256) {
    $errorText = 'independent method drift'
  }
  if ($script:steps.Count -ge 4 -and $script:steps[3].converter_log_sha256 -and
      (Observed-Sha (Join-Path $run 'model-run.log')) -ne $script:steps[3].converter_log_sha256) {
    $errorText = 'sealed converter log drift'
  }
  $raw = [ordered]@{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File | Sort-Object Name) {
    if ($file.Name -ne 'invocation.json') { $raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=(Get-Sha $file.FullName)} }
  }
  [ordered]@{schema='i05-var07-closure/v101';run_id=$runId;
    native_run_directory=$nativeRunDirectory;
    invocation_sha256=(Get-Sha (Join-Path $run 'invocation.json'));
    manifest_sha256=$manifestAfter;approval_sha256=$approvalAfter;approved_preflight_sha256=$preflightAfter;
    source_hashes_before=$before;source_hashes_after=$after;raw=$raw;step_error=$stepError;error=$errorText;
    publication_state='not_published'} | ConvertTo-Json -Depth 10 |
    Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
}

if ($PSVersionTable.PSVersion.Major -ne 5 -or -not $env:SSH_CONNECTION -or
    (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'actual SSH PowerShell5 session0 required' }
$ancestors = @()
$ancestorIds = @()
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorIds += [int]$ancestor.ProcessId
  $ancestorPid=$ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'sshd ancestry absent' }
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'native working directory absent' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$manifestShaAtLaunch=Get-Sha $manifestPath
Assert-JsonKeys $manifest @('schema','run_id','native_run_directory','file_line_ascii_bytes',
  'file_line_ascii_max','base_commit','contract_sha256','execution_binding_sha256',
  'input_sha256','source_inventory_sha256','runner_sha256','validator_sha256',
  'independent_reader_sha256','source_count','source_files','owned_source_count',
  'selected_reference_count','selected_unique_original_count',
  'accepted_source_pair_count','accepted_source_pair_unique_count','accepted_raw_count','excluded_raw_count',
  'archived_catalog_count','installed_source_count','runtime_source_count','historical_source_count',
  'catalog_prefix_entries',
  'live_catalog_prelaunch_pin','pure_tools','stages','native_commands','pure_checkers',
  'new_native_runs_authorized_by_manifest','independent_method_state') 'prelaunch manifest'
if ($manifest.schema -ne 'i05-var07-prelaunch-manifest/v101' -or
    $manifest.contract_sha256 -ne 'c34bb3d2b9c88763347f63e5bb111389db00e800d743ff74102e810eab6df0b7' -or
    $manifest.execution_binding_sha256 -ne (Get-Sha (Join-Path $case 'execution-contract.json')) -or
    $manifest.run_id -ne $runId -or
    -not ($manifest.native_run_directory -is [string]) -or
    $manifest.native_run_directory -cne $nativeRunDirectory -or
    $manifest.input_sha256 -ne (Get-Sha (Join-Path $case 'native-input.json')) -or
    $manifest.source_inventory_sha256 -ne (Get-Sha (Join-Path $case 'source-inventory.json')) -or
    $manifest.runner_sha256 -ne (Get-Sha $PSCommandPath) -or
    $manifest.validator_sha256 -ne (Get-Sha (Join-Path $case 'validate_native_cli.py')) -or
    $manifest.independent_reader_sha256 -ne (Get-Sha (Join-Path $case 'review\independent_reader.py')) -or
    $manifest.selected_reference_count -ne 100 -or
    $manifest.selected_unique_original_count -ne 98 -or
    $manifest.accepted_source_pair_count -ne 37 -or
    $manifest.accepted_source_pair_unique_count -ne 35 -or
    $manifest.accepted_raw_count -ne 24 -or $manifest.excluded_raw_count -ne 24 -or
    $manifest.archived_catalog_count -ne 2 -or
    $manifest.installed_source_count -ne 3 -or $manifest.runtime_source_count -ne 1 -or
    $manifest.historical_source_count -ne 2 -or
    $manifest.catalog_prefix_entries -ne 505 -or $manifest.native_commands -ne 4 -or
    $manifest.pure_checkers -ne 2 -or $manifest.new_native_runs_authorized_by_manifest -ne 0 -or
    -not ($manifest.owned_source_count -is [int] -or $manifest.owned_source_count -is [long]) -or
    $manifest.base_commit -cne '120adb3d8912acfe9965ea04c939867721f3ede3' -or
    $manifest.source_count -ne @($manifest.source_files).Count -or
    $manifest.source_count -ne ($manifest.owned_source_count + 103) -or
    (@($manifest.pure_tools) -join '|') -cne 'build.py|source_gate.py|self_check.py|make_source_inventory.py|make_prelaunch_manifest.py' -or
    (@($manifest.stages) -join '|') -cne 'import|export|check_import_export|calc|jsonreport|check_behavior' -or
     $manifest.independent_method_state -cne 'SOURCE_CONSTRUCTION_ONLY_NO_SSH_OR_NATIVE_APPROVAL' -or
    -not ($manifest.file_line_ascii_bytes -is [int] -or $manifest.file_line_ascii_bytes -is [long]) -or
    $manifest.file_line_ascii_bytes -ne 119 -or
    -not ($manifest.file_line_ascii_max -is [int] -or $manifest.file_line_ascii_max -is [long]) -or
    $manifest.file_line_ascii_max -ne 199) { throw 'manifest identity mismatch' }
$specialRoles=@{
  'owned:run_native_ssh.ps1'='run_native_ssh.ps1';
  'owned:validate_native_cli.py'='validate_native_cli.py';
  'owned:preserved-design/prospective-contract-v100.json'='preserved-design\prospective-contract-v100.json';
  'owned:execution-contract.json'='execution-contract.json';
  'owned:native-input.json'='native-input.json'
}
foreach ($key in $specialRoles.Keys) {
  $matches=@($manifest.source_files | Where-Object { $_.key -ceq $key })
  if ($matches.Count -ne 1 -or $matches[0].path -cne (Join-Path $case ($specialRoles[$key]))) {
    throw "manifest special source role differs: $key"
  }
}
$folded=@($manifest.source_files | ForEach-Object { $_.key.ToLowerInvariant() })
if (@($folded | Sort-Object -Unique).Count -ne $folded.Count) { throw 'manifest role key alias' }
foreach ($entry in $manifest.source_files) {
  Assert-JsonKeys $entry @('key','path','bytes','sha256','mode','attributes') 'manifest source role'
  if ($entry.key -isnot [string] -or $entry.path -isnot [string] -or
      -not [System.IO.Path]::IsPathRooted($entry.path) -or
      -not ($entry.bytes -is [int] -or $entry.bytes -is [long]) -or $entry.bytes -lt 0 -or
      $entry.sha256 -isnot [string] -or $entry.sha256 -notmatch '^[0-9a-f]{64}$' -or
      -not ($entry.mode -is [int] -or $entry.mode -is [long]) -or
      -not ($entry.attributes -is [int] -or $entry.attributes -is [long])) {
    throw 'manifest source role type/path/pin differs'
  }
}
$selectionPath=Join-Path $case 'source-maps\root-selection-record.json'
$selectionRole=@($manifest.source_files | Where-Object { $_.key -ceq 'owned:source-maps/root-selection-record.json' })
if ($selectionRole.Count -ne 1 -or $selectionRole[0].path -cne $selectionPath -or
    $selectionRole[0].sha256 -cne (Get-Sha $selectionPath)) {
  throw 'selection source role differs'
}
$selection=Get-Content -LiteralPath $selectionPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($selection.schema -cne 'i05-var07-root-selection-byte-audit/v100' -or
    $selection.protected_original_count -ne 98 -or $selection.role_reference_count -ne 100) {
  throw 'selected original roster differs'
}
$selectedRoles=@($manifest.source_files | Where-Object { $_.key -clike 'selected:*' })
if ($selectedRoles.Count -ne 100 -or $selectedRoles[0].key -cne 'selected:live' -or
    $selectedRoles[1].key -cne 'selected:catalog' -or
    $selectedRoles[2].key -cne 'selected:prior-map' -or
    $selectedRoles[3].key -cne 'selected:manual-sources') {
  throw 'selected role count or leading order differs'
}
$historicalRoles=@($manifest.source_files | Where-Object { $_.key -clike 'historical:*' })
if ($historicalRoles.Count -ne 2 -or
    $historicalRoles[0].key -cne 'historical:v100-author-freeze' -or
    $historicalRoles[1].key -cne 'historical:v100-static-no-go' -or
    $historicalRoles[0].path -cne (Join-Path $workingDirectory 'tmp\i05-var07-author-freeze-case-v100-20261009-01.json') -or
    $historicalRoles[1].path -cne (Join-Path $workingDirectory 'tmp\i05-var07-root-static-nogo-v100-20261009-01.json')) {
  throw 'prior static NO_GO custody role identity differs'
}
Assert-NativeRunPath
$mutex=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false
$ownedRun=$false
try {
  try { $acquired=$mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired=$true }
  if (-not $acquired) { throw 'host-wide native queue busy' }
  Assert-Guard
  Assert-NativeRunPath
  $before=Source-Hashes
  if ($before['owned:run_native_ssh.ps1'] -ne (Get-Sha $PSCommandPath)) { throw 'runner not source-pinned' }
  $pureRoot=Join-Path $case 'test-output'
  if (-not (Test-Path -LiteralPath $pureRoot)) { New-Item -ItemType Directory -Path $pureRoot | Out-Null }
  $pureMode=$(if ($PreflightOnly) {'preflight'} else {'native'})
  $pureDir=Join-Path $pureRoot ($pureMode + '-pure-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffffffZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
  New-Item -ItemType Directory -Path $pureDir | Out-Null
  $pureChecks=@()
  $pureReceiptPath=Join-Path $pureDir 'pure-proof.json'
  $pureProof=[ordered]@{schema='i05-var07-pure-proof/v101';
    mode=$(if ($PreflightOnly) {'preflight'} else {'native'});run_id=$runId;
    native_run_directory=$nativeRunDirectory;
    manifest_sha256=(Get-Sha $manifestPath);source_map_sha256=(Get-SourceMapSha $before);
    started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;
    status='started';error=$null;checks=$pureChecks}
  function Save-PureProof {
    $pureProof.checks=$pureChecks
    ConvertTo-Json -InputObject $pureProof -Depth 10 | Set-Content -LiteralPath $pureReceiptPath -Encoding UTF8
  }
  Save-PureProof
  try {
    foreach ($tool in @('build.py','source_gate.py','self_check.py','make_source_inventory.py','make_prelaunch_manifest.py')) {
      Assert-Guard
      $stem=[System.IO.Path]::GetFileNameWithoutExtension($tool)
      $stdout=Join-Path $pureDir ($stem + '-stdout.bin')
      $stderr=Join-Path $pureDir ($stem + '-stderr.bin')
      $arguments=('-X utf8 -B "{0}"' -f (Join-Path $case $tool))
      $started=(Get-Date).ToUniversalTime().ToString('o')
      $proofStep=[ordered]@{tool=$tool;program=$python;arguments=$arguments;
        started_utc=$started;completed_utc=$null;status='started';error=$null;
        child_pid=$null;child_session_id=$null;exit_code=$null;capture_error=$null;
        stdout_path=$stdout;stderr_path=$stderr;stdout_bytes=$null;stderr_bytes=$null;
        stdout_sha256=$null;stderr_sha256=$null}
      $pureChecks += $proofStep
      Save-PureProof
      try {
        $capture=Invoke-CapturedProcess $python $arguments $case $stdout $stderr 0
        $proofStep.child_pid=$capture.child_pid
        $proofStep.child_session_id=$capture.child_session_id
        $proofStep.exit_code=$capture.exit_code
        $proofStep.capture_error=$capture.capture_error
        $proofStep.stdout_path=$capture.stdout_path
        $proofStep.stderr_path=$capture.stderr_path
        $proofStep.stdout_bytes=$capture.stdout_bytes
        $proofStep.stderr_bytes=$capture.stderr_bytes
        $proofStep.stdout_sha256=$capture.stdout_sha256
        $proofStep.stderr_sha256=$capture.stderr_sha256
        $proofStep.status='completed'
      } catch {
        $proofStep.status='failed'
        $proofStep.error=$_.Exception.Message
        throw
      } finally {
        $proofStep.completed_utc=(Get-Date).ToUniversalTime().ToString('o')
        Save-PureProof
      }
      Assert-Guard
      Assert-SuccessfulCapture $capture 0 | Out-Null
      if ($capture.stderr_bytes -ne 0) { throw "read-only $tool wrote stderr" }
    }
    $afterPure=Source-Hashes
    foreach ($key in $before.Keys) {
      if ($afterPure[$key] -ne $before[$key]) { throw "source changed during pure checks: $key" }
    }
    $pureProof.source_hashes_after=$afterPure
    $pureProof.status='passed'
  } catch {
    $pureProof.status='failed'
    $pureProof.error=$_.Exception.Message
    throw
  } finally {
    $pureProof.completed_utc=(Get-Date).ToUniversalTime().ToString('o')
    Save-PureProof
  }
  $run=$nativeRunDirectory
  if (Test-Path -LiteralPath $run) { throw 'reserved run path already exists' }
  Assert-Guard
  if ($PreflightOnly) {
    $preflight=Join-Path $case ('review\preflight-ssh0-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ') + '.json')
    if (Test-Path -LiteralPath $preflight) { throw 'unique preflight receipt path already exists' }
    [ordered]@{schema='i05-var07-ssh-preflight/v101';run_id=$runId;
      native_run_directory=$nativeRunDirectory;run_dirs_absent=$true;
      file_line_ascii_bytes=119;file_line_ascii_max=199;native_run_path_ancestors_no_reparse=$true;
      ssh_session=0;ps_major=5;ssh_ancestors=$ancestors;mutex_free=$true;wts_active_gui_count=1;
      gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
      selected_reference_count=100;selected_unique_original_count=98;
      accepted_source_pair_count=37;accepted_source_pair_unique_count=35;accepted_raw_count=24;excluded_raw_count=24;
      archived_catalog_count=2;installed_source_count=3;runtime_source_count=1;historical_source_count=2;catalog_prefix_entries=505;
      manifest_sha256=(Get-Sha $manifestPath);source_map_sha256=(Get-SourceMapSha $before);
      source_hashes=$before;source_hashes_after_pure=$afterPure;
      pure_proof_directory=$pureDir;pure_proof_path=$pureReceiptPath;
      pure_proof_sha256=(Get-Sha $pureReceiptPath);pure_checks=$pureChecks;
      native_process_started=$false} | ConvertTo-Json -Depth 10 |
      Set-Content -LiteralPath $preflight -Encoding UTF8
    Write-Output $preflight
    return
  }
  if (-not (Test-Path -LiteralPath $approvalPath -PathType Leaf)) { throw 'independent prelaunch approval absent' }
  $approval=Get-Content -LiteralPath $approvalPath -Raw -Encoding UTF8 | ConvertFrom-Json
  Assert-JsonKeys $approval @('schema','decision','run_id','native_run_directory',
    'manifest_sha256','runner_sha256','validator_sha256','contract_sha256',
    'execution_binding_sha256','input_sha256','source_map_sha256',
    'independent_reader_sha256','preflight_relative_path','preflight_sha256') 'independent approval'
  Assert-RunDirectory $approval.native_run_directory $nativeRunDirectory 'approval native_run_directory'
  if ($approval.schema -ne 'i05-var07-independent-prelaunch-go/v101' -or
      $approval.decision -ne 'GO_PRELAUNCH' -or $approval.manifest_sha256 -ne (Get-Sha $manifestPath) -or
      $approval.runner_sha256 -ne $before['owned:run_native_ssh.ps1'] -or
      $approval.validator_sha256 -ne $before['owned:validate_native_cli.py'] -or
       $approval.contract_sha256 -ne $before['owned:preserved-design/prospective-contract-v100.json'] -or
      $approval.execution_binding_sha256 -ne $before['owned:execution-contract.json'] -or
      $approval.input_sha256 -ne $before['owned:native-input.json'] -or $approval.run_id -ne $runId -or
      $approval.source_map_sha256 -ne (Get-SourceMapSha $before) -or
      $approval.independent_reader_sha256 -notmatch '^[0-9a-f]{64}$' -or
      $approval.independent_reader_sha256 -ne (Get-Sha (Join-Path $case 'review\independent_reader.py'))) {
    throw 'independent approval does not bind exact frozen case'
  }
  $preflightPath=Assert-PreflightReceiptPath $case $approval.preflight_relative_path $approval.preflight_sha256 `
                   $runId $nativeRunDirectory (Get-Sha $manifestPath) $before
  $approvalSha=Get-Sha $approvalPath
  Assert-NativeRunPath
  $nativeParent=Split-Path -Parent $nativeRunDirectory
  if (-not (Test-Path -LiteralPath $nativeParent -PathType Container)) {
    New-Item -ItemType Directory -Path $nativeParent | Out-Null
  }
  if (Test-Path -LiteralPath $run) { throw 'reserved run path appeared' }
  New-Item -ItemType Directory -Path $run | Out-Null
  $ownedRun=$true
  Copy-Item -LiteralPath (Join-Path $case 'native-input.json') -Destination (Join-Path $run 'input.json')
  if ((Get-Sha (Join-Path $run 'input.json')) -ne $before['owned:native-input.json']) { throw 'input copy drift' }
  $commands=@(
    [ordered]@{name='import';program=$exe;arguments=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'input.json'),(Join-Path $run 'model.sxi'),(Join-Path $run 'import.log'))},
    [ordered]@{name='export';program=$exe;arguments=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f (Join-Path $run 'model.sxi'),(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'export.log'))},
    [ordered]@{name='calc';program=$exe;arguments=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f (Join-Path $run 'model.sxi'),(Join-Path $run 'model-run.log'))},
    [ordered]@{name='jsonreport';program=$exe;arguments=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f (Join-Path $run 'model.sxo'),(Join-Path $run 'report-raw.json'),(Join-Path $run 'report-export.log'))}
  )
  $checkerCommands=@(
    [ordered]@{name='check_import_export';program=$python;
      arguments=('-X utf8 -B "{0}" --run-dir "{1}"' -f (Join-Path $case 'check_roundtrip.py'),$run)},
    [ordered]@{name='check_behavior';program=$python;
      arguments=('-X utf8 -B "{0}" --run-dir "{1}"' -f (Join-Path $case 'validate_native_cli.py'),$run)}
  )
  [ordered]@{schema='i05-var07-invocation/v101';run_id=$runId;created_utc=(Get-Date).ToUniversalTime().ToString('o');
    original_run_dir=$run;native_run_directory=$nativeRunDirectory;
     input_sha256=$before['owned:native-input.json'];contract_sha256=$before['owned:preserved-design/prospective-contract-v100.json'];
    manifest_sha256=(Get-Sha $manifestPath);approval_sha256=$approvalSha;approved_preflight_path=$preflightPath;
    approved_preflight_sha256=$approval.preflight_sha256;independent_reader_sha256=$approval.independent_reader_sha256;
    runner_script_sha256=$before['owned:run_native_ssh.ps1'];session_id=0;ssh_ancestors=$ancestors;
    gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
    queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$workingDirectory;
    planned_commands=$commands;planned_checkers=$checkerCommands;
    source_hashes_before=$before;source_hashes_after_pure=$afterPure;pure_proof_path=$pureReceiptPath;
    pure_proof_sha256=(Get-Sha $pureReceiptPath);pure_checks=$pureChecks;
    publication_state='not_published'} | ConvertTo-Json -Depth 10 |
    Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps=@()
  $errorText=$null
  try {
    Run-Step $run 'import' $commands[0].program $commands[0].arguments @('model.sxi','import.log') $false
    Run-Step $run 'export' $commands[1].program $commands[1].arguments @('roundtrip-raw.json','export.log') $false
    Run-Step $run 'check_import_export' $checkerCommands[0].program $checkerCommands[0].arguments @('roundtrip-raw.json') $true
    Run-Step $run 'calc' $commands[2].program $commands[2].arguments @('model.sxo','model.log','model-run.log') $false
    if ((Get-Sha (Join-Path $run 'model-run.log')) -cne $steps[3].converter_log_sha256 -or
        -not (Get-Item -LiteralPath (Join-Path $run 'model-run.log')).IsReadOnly) {
      throw 'calc converter log seal drift before converter gate'
    }
    Assert-ConverterLog $run $steps[3].converter_log_sha256
    $steps[3].converter_log_validated=$true
    Save-Steps $run
    Run-Step $run 'jsonreport' $commands[3].program $commands[3].arguments @('report-raw.json','report-export.log') $false
    Run-Step $run 'check_behavior' $checkerCommands[1].program $checkerCommands[1].arguments @('report-raw.json') $true
  } catch { $errorText=$_.Exception.Message }
  Seal-Run $run $errorText
  Assert-Guard
  [ordered]@{decision='NATIVE_CHILD_COMPLETED';run_id=$runId} | ConvertTo-Json
} catch {
  $message=$_.Exception.Message
  $run=$nativeRunDirectory
  if ($ownedRun -and (Test-Path -LiteralPath $run) -and
      -not (Test-Path -LiteralPath (Join-Path $run 'failure-seal.json'))) {
    $files=[ordered]@{}
    foreach ($file in Get-ChildItem -LiteralPath $run -File | Sort-Object Name) {
      $files[$file.Name]=[ordered]@{bytes=$file.Length;sha256=(Get-Sha $file.FullName)}
    }
    [ordered]@{schema='i05-var07-failure-seal/v101';run_id=$runId;
      native_run_directory=$nativeRunDirectory;error=$message;files=$files;
      publication_state='excluded'} | ConvertTo-Json -Depth 10 |
      Set-Content -LiteralPath (Join-Path $run 'failure-seal.json') -Encoding UTF8
  }
  throw $message
} finally {
  if ($acquired) { $mutex.ReleaseMutex() | Out-Null }
  $mutex.Dispose()
}

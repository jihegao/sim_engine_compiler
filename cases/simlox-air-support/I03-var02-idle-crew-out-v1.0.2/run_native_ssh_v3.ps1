param([switch]$PreflightOnly)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$manifestPath = Join-Path $case 'prelaunch-manifest-v2.json'
$approvalPath = Join-Path $case 'review\independent-prelaunch-go.json'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$runId = 'i03-var02-idle-out-v102-ssh-20261007-01'
. (Join-Path $case 'captured_process.ps1')
. (Join-Path $case 'preflight_receipt.ps1')
. (Join-Path $case 'checker_receipt.ps1')

function Get-Sha([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Observed-Sha([string]$path) {
  if (Test-Path -LiteralPath $path -PathType Leaf) { return Get-Sha $path }
  return $null
}
function Source-Hashes {
  $result = [ordered]@{}
  foreach ($entry in $manifest.source_files) {
    if (-not (Test-Path -LiteralPath $entry.path -PathType Leaf)) { throw "source absent: $($entry.key)" }
    $file = Get-Item -LiteralPath $entry.path
    $hash = Get-Sha $entry.path
    if ($hash -ne $entry.sha256 -or $file.Length -ne $entry.bytes) { throw "source changed: $($entry.key)" }
    $result[$entry.key] = $hash
  }
  return $result
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
  Assert-Gui
  Assert-Wts
  Assert-CompetingRunner
}
function Save-Steps([string]$run) {
  ConvertTo-Json -InputObject $script:steps -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
}
function Run-Step([string]$run,[string]$name,[string]$program,[string]$arguments,
                  [string[]]$required,[bool]$checker) {
  $step = [ordered]@{name=$name;arguments=$arguments;started_utc=(Get-Date).ToUniversalTime().ToString('o');
    completed_utc=$null;child_pid=$null;child_session_id=$null;exit_code=$null;capture_error=$null;
    stdout_path=$null;stderr_path=$null;gui_preserved=$false;status='started';error=$null}
  $script:steps += $step
  try {
    Save-Steps $run
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
    Assert-Guard
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
      Assert-CheckerVerdict $name $stdout $runId $before.child_input $export | Out-Null
    }
    $step.status = 'completed'
  } catch { $step.status='failed';$step.error=$_.Exception.Message;throw }
  finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o');Save-Steps $run }
}
function Seal-Run([string]$run,[string]$errorText) {
  $stepError=$errorText
  $after = Observed-Hashes
  foreach ($key in $before.Keys) { if ($before[$key] -ne $after[$key]) { $errorText = "source drift: $key" } }
  $manifestAfter = Observed-Sha $manifestPath
  $approvalAfter = Observed-Sha $approvalPath
  $preflightAfter = Observed-Sha $script:preflightPath
  if ($manifestAfter -ne $approval.manifest_sha256 -or $approvalAfter -ne $script:approvalSha -or
      $preflightAfter -ne $approval.preflight_sha256) { $errorText = 'authorization file drift' }
  if ((Observed-Sha (Join-Path $case 'review\independent_replay_v3.py')) -ne $approval.independent_replay_sha256) {
    $errorText = 'independent method drift'
  }
  $raw = [ordered]@{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File | Sort-Object Name) {
    if ($file.Name -ne 'invocation.json') { $raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=(Get-Sha $file.FullName)} }
  }
  [ordered]@{schema='i03-var02-v102-closure/v1';run_id=$runId;
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
if ($manifest.schema -ne 'i03-var02-v102-prelaunch-manifest/v2' -or
    $manifest.contract_sha256 -ne '1f058ae8706d4de81c28099b6580619eb4cb879e20314619f387839d9150ee29' -or
    $manifest.run_id -ne $runId) { throw 'manifest identity mismatch' }
$mutex=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false
$ownedRun=$false
try {
  try { $acquired=$mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired=$true }
  if (-not $acquired) { throw 'host-wide native queue busy' }
  Assert-Guard
  $before=Source-Hashes
  if ($before.runner_script -ne (Get-Sha $PSCommandPath)) { throw 'runner not source-pinned' }
  foreach ($tool in @('build.py','verify_sources.py','test_sealed_catalog.py','self_check.py','make_prelaunch_manifest_v2.py')) {
    Assert-Guard
    & $python -X utf8 -B (Join-Path $case $tool) | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "read-only $tool failed" }
    Assert-Guard
  }
  $run=Join-Path (Join-Path $case 'runs') $runId
  if (Test-Path -LiteralPath $run) { throw 'reserved run path already exists' }
  Assert-Guard
  if ($PreflightOnly) {
    $preflight=Join-Path $case ('review\preflight-ssh0-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ') + '.json')
    if (Test-Path -LiteralPath $preflight) { throw 'unique preflight receipt path already exists' }
    [ordered]@{schema='i03-var02-v102-ssh-preflight/v1';run_id=$runId;run_dirs_absent=$true;
      ssh_session=0;ps_major=5;ssh_ancestors=$ancestors;mutex_free=$true;wts_active_gui_count=1;
      gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
      accepted_raw_seals=32;accepted_closures=1;accepted_invocations=1;
      manifest_sha256=(Get-Sha $manifestPath);source_map_sha256=(Get-SourceMapSha $before);
      source_hashes=$before;native_process_started=$false} | ConvertTo-Json -Depth 10 |
      Set-Content -LiteralPath $preflight -Encoding UTF8
    Write-Output $preflight
    return
  }
  if (-not (Test-Path -LiteralPath $approvalPath -PathType Leaf)) { throw 'independent prelaunch approval absent' }
  $approval=Get-Content -LiteralPath $approvalPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($approval.schema -ne 'i03-var02-v102-independent-prelaunch-go/v1' -or
      $approval.decision -ne 'GO_PRELAUNCH' -or $approval.manifest_sha256 -ne (Get-Sha $manifestPath) -or
      $approval.runner_sha256 -ne $before.runner_script -or
      $approval.validator_sha256 -ne $before.behavior_validator -or
      $approval.contract_sha256 -ne $before.child_contract -or
      $approval.input_sha256 -ne $before.child_input -or $approval.run_id -ne $runId -or
      $approval.source_map_sha256 -ne (Get-SourceMapSha $before) -or
      $approval.independent_replay_sha256 -notmatch '^[0-9a-f]{64}$' -or
      $approval.independent_replay_sha256 -ne (Get-Sha (Join-Path $case 'review\independent_replay_v3.py'))) {
    throw 'independent approval does not bind exact frozen case'
  }
  $preflightPath=Assert-PreflightReceiptPath $case $approval.preflight_relative_path $approval.preflight_sha256 `
                   $runId (Get-Sha $manifestPath) $before
  $approvalSha=Get-Sha $approvalPath
  New-Item -ItemType Directory -Path (Join-Path $case 'runs') -Force | Out-Null
  if (Test-Path -LiteralPath $run) { throw 'reserved run path appeared' }
  New-Item -ItemType Directory -Path $run | Out-Null
  $ownedRun=$true
  Copy-Item -LiteralPath (Join-Path $case 'native-input.json') -Destination (Join-Path $run 'input.json')
  if ((Get-Sha (Join-Path $run 'input.json')) -ne $before.child_input) { throw 'input copy drift' }
  $commands=@(
    [ordered]@{name='import';arguments=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'input.json'),(Join-Path $run 'model.sxi'),(Join-Path $run 'import.log'))},
    [ordered]@{name='export';arguments=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f (Join-Path $run 'model.sxi'),(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'export.log'))},
    [ordered]@{name='calc';arguments=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f (Join-Path $run 'model.sxi'),(Join-Path $run 'run.log'))},
    [ordered]@{name='jsonreport';arguments=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f (Join-Path $run 'model.sxo'),(Join-Path $run 'report-raw.json'),(Join-Path $run 'report-export.log'))}
  )
  [ordered]@{schema='i03-var02-v102-invocation/v1';run_id=$runId;created_utc=(Get-Date).ToUniversalTime().ToString('o');
    original_run_dir=$run;input_sha256=$before.child_input;contract_sha256=$before.child_contract;
    manifest_sha256=(Get-Sha $manifestPath);approval_sha256=$approvalSha;approved_preflight_path=$preflightPath;
    approved_preflight_sha256=$approval.preflight_sha256;independent_replay_sha256=$approval.independent_replay_sha256;
    runner_script_sha256=$before.runner_script;session_id=0;ssh_ancestors=$ancestors;
    gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
    queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$workingDirectory;planned_commands=$commands;
    source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 10 |
    Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps=@()
  $errorText=$null
  try {
    Run-Step $run 'import' $exe $commands[0].arguments @('model.sxi','import.log') $false
    Run-Step $run 'export' $exe $commands[1].arguments @('roundtrip-raw.json','export.log') $false
    $args='-X utf8 -B "{0}" "{1}"' -f (Join-Path $case 'check_roundtrip.py'),$run
    Run-Step $run 'check_import_export' $python $args @('roundtrip-raw.json') $true
    Run-Step $run 'calc' $exe $commands[2].arguments @('model.sxo','model.log','run.log') $false
    Run-Step $run 'jsonreport' $exe $commands[3].arguments @('report-raw.json','report-export.log') $false
    $args='-X utf8 -B "{0}" "{1}"' -f (Join-Path $case 'validate_native_cli.py'),$run
    Run-Step $run 'check_behavior' $python $args @('report-raw.json') $true
  } catch { $errorText=$_.Exception.Message }
  Seal-Run $run $errorText
  Assert-Guard
  [ordered]@{decision='NATIVE_CHILD_COMPLETED';run_id=$runId} | ConvertTo-Json
} catch {
  $message=$_.Exception.Message
  $run=Join-Path (Join-Path $case 'runs') $runId
  if ($ownedRun -and (Test-Path -LiteralPath $run) -and
      -not (Test-Path -LiteralPath (Join-Path $run 'failure-seal.json'))) {
    $files=[ordered]@{}
    foreach ($file in Get-ChildItem -LiteralPath $run -File | Sort-Object Name) {
      $files[$file.Name]=[ordered]@{bytes=$file.Length;sha256=(Get-Sha $file.FullName)}
    }
    [ordered]@{schema='i03-var02-v102-failure-seal/v1';run_id=$runId;error=$message;files=$files;
      publication_state='excluded'} | ConvertTo-Json -Depth 10 |
      Set-Content -LiteralPath (Join-Path $run 'failure-seal.json') -Encoding UTF8
  }
  throw $message
} finally {
  if ($acquired) { $mutex.ReleaseMutex() | Out-Null }
  $mutex.Dispose()
}

param([switch]$PreflightOnly)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$root = Split-Path $case -Parent
$manifestPath = Join-Path $case 'prelaunch-manifest.json'
$approvalPath = Join-Path $case 'review\independent-prelaunch-go.json'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$parentRun = Join-Path $root 'C06-alternative-resource-v1.0.0\runs\c06-primary-0-artf-2-20260930-01'
$prereqRun = 'C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support\C03-shared-crew-formation-v1.0.2\runs\c03-v102-staff2-ssh-20260929-04'
$runIds = [ordered]@{
  factor1 = 'c06-var03-v101-factor1-ssh-20261007-01'
  factor3 = 'c06-var03-v101-factor3-ssh-20261007-01'
}

function Get-Sha([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Assert-Raw([string]$directory,[string]$runId,[int]$count,[string]$closureSha) {
  $path = Join-Path $directory 'closure.json'
  if ((Get-Sha $path) -ne $closureSha) { throw "accepted closure SHA differs: $runId" }
  $data = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
  if ($data.run_id -ne $runId -or @($data.raw.PSObject.Properties).Count -ne $count) { throw "accepted closure identity/count differs: $runId" }
  foreach ($entry in $data.raw.PSObject.Properties) {
    $file = Join-Path $directory $entry.Name
    if (-not (Test-Path -LiteralPath $file) -or (Get-Item -LiteralPath $file).Length -ne $entry.Value.bytes -or (Get-Sha $file) -ne $entry.Value.sha256) {
      throw "accepted raw seal differs: $runId/$($entry.Name)"
    }
  }
}
function Source-Hashes {
  $result = [ordered]@{}
  foreach ($entry in $manifest.source_files) {
    if (-not (Test-Path -LiteralPath $entry.path)) { throw "missing source $($entry.key)" }
    $file = Get-Item -LiteralPath $entry.path
    $actual = Get-Sha $entry.path
    if ($actual -ne $entry.sha256 -or $file.Length -ne $entry.bytes) { throw "source SHA/size differs: $($entry.key)" }
    $result[$entry.key] = $actual
  }
  return $result
}
function Assert-Gui {
  $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne 1 -or -not $p[0].Responding -or
      ([DateTimeOffset]$p[0].StartTime.ToUniversalTime()).ToUnixTimeMilliseconds() -ne 1790590196826) {
    throw 'protected GUI PID/session/start/responding changed'
  }
}
function Seal-Run([string]$run,[string]$runId,[object]$before,[string]$errorText) {
  $after = Source-Hashes
  foreach ($key in $before.Keys) { if ($before[$key] -ne $after[$key]) { $errorText = "source changed during native steps: $key" } }
  $raw = [ordered]@{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File | Sort-Object Name) {
    if ($file.Name -eq 'invocation.json') { continue }
    $raw[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-Sha $file.FullName)}
  }
  [ordered]@{schema='c06-var03-v101-closure/v1';run_id=$runId;invocation_sha256=(Get-Sha (Join-Path $run 'invocation.json'));
    source_hashes_before=$before;source_hashes_after=$after;raw=$raw;error=$errorText;publication_state='not_published'} |
    ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
}
function Native-Step([string]$run,[string]$name,[string]$arguments,[string[]]$required) {
  $step = [ordered]@{name=$name;arguments=$arguments;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;
    exit_code=$null;gui_preserved=$false;status='started';error=$null}
  $script:steps += $step
  try {
    Assert-Gui
    $native = Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru
    if (-not $native.WaitForExit(300000)) {
      Stop-Process -Id $native.Id -Force -ErrorAction SilentlyContinue
      $native.WaitForExit(10000) | Out-Null
      throw "$name watchdog expired; stopped only launched PID $($native.Id)"
    }
    $step.exit_code = $native.ExitCode
    Assert-Gui
    $step.gui_preserved = $true
    if ($native.ExitCode -ne 0) { throw "$name exit=$($native.ExitCode)" }
    foreach ($relative in $required) {
      $path = Join-Path $run $relative
      if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -le 4) { throw "$name output missing/empty: $relative" }
    }
    $step.status = 'completed'
  } catch { $step.status='failed';$step.error=$_.Exception.Message;throw }
  finally {
    $step.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
    ConvertTo-Json -InputObject $script:steps -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
  }
}
function Check-Step([string]$run,[string]$name,[string]$scriptPath,[string]$arm,[string]$output) {
  $step = [ordered]@{name=$name;arguments=@($scriptPath,$run,$arm);started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;
    exit_code=$null;gui_preserved=$false;status='started';error=$null}
  $script:steps += $step
  try {
    Assert-Gui
    & $python $scriptPath $run $arm | Set-Content -LiteralPath (Join-Path $run $output) -Encoding UTF8
    $step.exit_code = $LASTEXITCODE
    Assert-Gui
    $step.gui_preserved = $true
    if ($step.exit_code -ne 0) { throw "$name rejected native result" }
    $step.status = 'completed'
  } catch { $step.status='failed';$step.error=$_.Exception.Message;throw }
  finally {
    $step.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
    ConvertTo-Json -InputObject $script:steps -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
  }
}

if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'actual SSH session 0 required' }
$ancestors = @()
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'sshd ancestry absent' }
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'native working directory absent' }
if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'prelaunch source manifest absent' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.schema -ne 'c06-var03-v101-prelaunch-manifest/v1' -or $manifest.contract_sha256 -ne '48a29f63e819e85dc3f9de856199c63441f32f34104dade338ef1ca246bd2384') { throw 'prelaunch manifest identity/contract differs' }
$before = Source-Hashes
if ($before.runner_script -ne (Get-Sha $PSCommandPath)) { throw 'runner not pinned by manifest' }
& $python (Join-Path $case 'build.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen builder verification failed' }
Assert-Raw $parentRun 'c06-primary-0-artf-2-20260930-01' 12 $manifest.accepted_parent_closure_sha256
Assert-Raw $prereqRun 'c03-v102-staff2-ssh-20260929-04' 11 $manifest.accepted_c03_closure_sha256
foreach ($arm in $runIds.Keys) { if (Test-Path -LiteralPath (Join-Path (Join-Path $case 'runs') $runIds[$arm])) { throw "run directory already exists: $arm" } }
$mutex = [System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired = $false
try {
  try { $acquired = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide native queue busy' }
  Assert-Gui
  $sessions = @(qwinsta 2>&1)
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match '^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+1\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)' }).Count -ne 1) { throw 'GUI session not active' }
  if ($PreflightOnly) {
    $preflight = Join-Path $case ('review\preflight-ssh0-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ') + '.json')
    [ordered]@{schema='c06-var03-v101-ssh-preflight/v1';run_ids=@($runIds.Values);run_dirs_absent=$true;ssh_session=0;
      ssh_ancestors=$ancestors;mutex_free=$true;gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
      accepted_parent_raw_seals=12;accepted_c03_raw_seals=11;manifest_sha256=(Get-Sha $manifestPath);source_hashes=$before;
      native_process_started=$false} | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $preflight -Encoding UTF8
    Write-Output $preflight
    return
  }
  if (-not (Test-Path -LiteralPath $approvalPath)) { throw 'independent exact-file prelaunch approval absent' }
  $approval = Get-Content -LiteralPath $approvalPath -Raw | ConvertFrom-Json
  if ($approval.decision -ne 'GO_PRELAUNCH' -or $approval.manifest_sha256 -ne (Get-Sha $manifestPath) -or
      $approval.runner_sha256 -ne $before.runner_script -or $approval.validator_sha256 -ne $before.behavior_validator -or
      $approval.contract_sha256 -ne $before.child_contract -or $approval.factor1_input_sha256 -ne $before.factor1_input -or
      $approval.factor3_input_sha256 -ne $before.factor3_input -or
      @($approval.run_ids).Count -ne 2 -or $approval.run_ids[0] -ne $runIds.factor1 -or $approval.run_ids[1] -ne $runIds.factor3) { throw 'independent approval does not bind frozen pair' }
  $preflightPath = Join-Path $case $approval.preflight_relative_path
  if (-not $preflightPath.StartsWith((Join-Path $case 'review\'),[System.StringComparison]::OrdinalIgnoreCase) -or
      (Get-Sha $preflightPath) -ne $approval.preflight_sha256) { throw 'approved SSH preflight seal differs' }
  New-Item -ItemType Directory -Path (Join-Path $case 'runs') -Force | Out-Null
  foreach ($arm in $runIds.Keys) {
    $runId = $runIds[$arm]
    $run = Join-Path (Join-Path $case 'runs') $runId
    if (Test-Path -LiteralPath $run) { throw "run directory appeared: $runId" }
    New-Item -ItemType Directory -Path $run | Out-Null
    $input = Join-Path $case ($arm + '-input.json')
    Copy-Item -LiteralPath $input -Destination (Join-Path $run 'input.json')
    if ((Get-Sha (Join-Path $run 'input.json')) -ne $before[($arm + '_input')]) { throw "input copy changed: $arm" }
    $commands = @(
      [ordered]@{name='import';arguments=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'input.json'),(Join-Path $run 'model.sxi'),(Join-Path $run 'import.log'))},
      [ordered]@{name='export';arguments=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f (Join-Path $run 'model.sxi'),(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'export.log'))},
      [ordered]@{name='calc';arguments=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f (Join-Path $run 'model.sxi'),(Join-Path $run 'run.log'))},
      [ordered]@{name='jsonreport';arguments=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f (Join-Path $run 'model.sxo'),(Join-Path $run 'report-raw.json'),(Join-Path $run 'report-export.log'))}
    )
    [ordered]@{schema='c06-var03-v101-invocation/v1';run_id=$runId;arm=$arm;created_utc=(Get-Date).ToUniversalTime().ToString('o');
      original_run_dir=$run;input_sha256=$before[($arm + '_input')];contract_sha256=$before.child_contract;
      manifest_sha256=(Get-Sha $manifestPath);runner_script_sha256=$before.runner_script;execution_mode='ssh_cli_v1';session_id=0;
      ssh_ancestors=$ancestors;gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
      queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$workingDirectory;planned_commands=$commands;
      source_hashes_before=$before;publication_state='not_published'} |
      ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
    $steps = @()
    $errorText = $null
    try {
      Native-Step $run 'import' $commands[0].arguments @('model.sxi','import.log')
      Native-Step $run 'export' $commands[1].arguments @('roundtrip-raw.json','export.log')
      Check-Step $run 'check_import_export' (Join-Path $case 'check_roundtrip.py') $arm 'roundtrip-validation.json'
      Native-Step $run 'calc' $commands[2].arguments @('model.sxo','model.log','run.log')
      $log = Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw
      $warnings = @([regex]::Matches($log,'warning\s*#(\d+)',[System.Text.RegularExpressions.RegexOptions]::IgnoreCase) | ForEach-Object { $_.Groups[1].Value } | Sort-Object)
      if ($log -notmatch 'Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0' -or
          ($warnings -join ',') -ne '108,126') { throw 'strict converter 0/2/0 warnings108/126 gate failed' }
      Native-Step $run 'jsonreport' $commands[3].arguments @('report-raw.json','report-export.log')
      Check-Step $run 'check_behavior' (Join-Path $case 'validate_native_cli.py') $arm 'author-validation.json'
    } catch { $errorText = $_.Exception.Message }
    Seal-Run $run $runId $before $errorText
    Assert-Gui
  }
  [ordered]@{decision='NATIVE_PAIR_COMPLETED';run_ids=@($runIds.Values)} | ConvertTo-Json
} catch {
  $message = $_.Exception.Message
  foreach ($runId in $runIds.Values) {
    $run = Join-Path (Join-Path $case 'runs') $runId
    if (-not (Test-Path -LiteralPath $run) -or (Test-Path -LiteralPath (Join-Path $run 'failure-seal.json'))) { continue }
    $files = [ordered]@{}
    foreach ($file in Get-ChildItem -LiteralPath $run -File | Sort-Object Name) {
      $files[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-Sha $file.FullName)}
    }
    [ordered]@{schema='c06-var03-v101-failure-seal/v1';run_id=$runId;error=$message;files=$files;publication_state='excluded'} |
      ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $run 'failure-seal.json') -Encoding UTF8
  }
  throw $message
} finally {
  if ($acquired) { $mutex.ReleaseMutex() | Out-Null }
  $mutex.Dispose()
}

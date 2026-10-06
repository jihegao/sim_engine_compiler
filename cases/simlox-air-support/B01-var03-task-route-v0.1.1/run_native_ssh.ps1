param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
  [switch]$PreflightOnly
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$root = Split-Path $case -Parent
$run = Join-Path (Join-Path $case 'runs') $RunId
$parent = Join-Path $root 'B03-explicit-cold-hot-v1.0.2'
$parentRun = 'C:\Users\user\dev\sim_engine_compiler-b03-v102\cases\simlox-air-support\B03-explicit-cold-hot-v1.0.2\runs\b03-v102-ssh-20260929-02'
$prereq = Join-Path $root 'A02-single-aircraft-repeated-missions'
$previous = Join-Path $root 'B01-var03-task-route-v0.1.0'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary = 'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$approvalPath = Join-Path $case 'review\independent-prelaunch-go.json'
$inputSha = '0cdb2bb68dcd49197988caba76b8d41e700b774139da98f33296c74c0d0d3c7b'
$contractSha = 'c06ef07a090403ca77f04189f49251bffec3c79cff5e77d5ae19cad10df426bc'
if ($RunId -ne 'b01-var03-task-route-v011-ssh-20261006-01') { throw 'unreviewed run identity' }
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'actual SSH session 0 required' }
$ancestors = @()
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'sshd ancestry not verified' }
if (Test-Path -LiteralPath $run) { throw 'immutable run directory already exists' }
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned native working directory absent' }

$sourcePaths = [ordered]@{
  child_input = (Join-Path $case 'native-input.json')
  child_contract = (Join-Path $case 'contract.json')
  contract_review = (Join-Path $case 'review\independent-contract-go-2026-10-06.md')
  builder = (Join-Path $case 'build.py')
  parent_diff_checker = (Join-Path $case 'check_parent_diff.py')
  roundtrip_checker = (Join-Path $case 'check_roundtrip.py')
  shared_parser = (Join-Path $root 'tools\validate_native.py')
  behavior_validator = (Join-Path $case 'validate_native_cli.py')
  runner_script = $PSCommandPath
  accepted_input = (Join-Path $parent 'native-input.json')
  accepted_contract = (Join-Path $parent 'contract.json')
  accepted_diff = (Join-Path $parent 'parent-diff.json')
  accepted_evidence = (Join-Path $parent 'evidence-2026-09-29.md')
  accepted_verdict = (Join-Path $parent 'review\independent-readonly-2026-09-29.json')
  accepted_closure = (Join-Path $parentRun 'closure.json')
  prereq_scope = (Join-Path $prereq 'cli-scope-signoff-2026-09-29.md')
  previous_contract = (Join-Path $previous 'contract.json')
  previous_nogo_review = (Join-Path $previous 'review\independent-contract-nogo-2026-10-06.md')
  installed_exe = $exe
  installed_manual = $manual
  installed_dictionary = $dictionary
  python = $python
}
$expected = @{
  child_input = $inputSha
  child_contract = $contractSha
  contract_review = '78843be6fbde1f8e9dc4388ad5bf0fa5595daf19cd6e389493fdc85f64bca0df'
  builder = '459a2a0bcbab69d4e7382186f57584d060d177b783db6ecf68f38b990fc01a98'
  parent_diff_checker = '3155000061f837494c631ad0e1134e5b0cfc0898739fe3ba256d0f3594c4ae3e'
  roundtrip_checker = 'ea4e8a7caba376534b6b5bf431d80181d4f564b68b6778553caf5c1081c91323'
  shared_parser = '43b42fbc5f6d2b9ecbeb82b1419224d6a99025c1be5c600dd959f77d362b6354'
  behavior_validator = 'e8a65628c7d0d1670cd0f1aa163a4dc4b4905411641eaac01472dff9a9844243'
  accepted_input = '9c6b3c8955089b89caa1a71634eb78e9fd52069d5d710273e3a6bc710e19222c'
  accepted_contract = '0d3d18196ce57dcbc8f36070ac53c532cdbaa313e0b9088eca8974af8a35127a'
  accepted_diff = 'b1480f9f3f414feb84ab08448f156e25aee15d8ee1e90e56fb652d1f87a13283'
  accepted_evidence = '6806694862a60bc135af6956f21f8386f44cc4f7d9e7671ce3340d0f4a00e94c'
  accepted_verdict = '3d7ea0b32bd554f8e8f49267d330e8150fc82611e79470736005042ab8ab5a8f'
  accepted_closure = '66bc79cf8609d89c5625299c7e61ede4f6f422e80af22e33bdbe166e18a6d96d'
  prereq_scope = '608eef828a65ef7a8c738a3ec227b890421c29248ee8addd9e992a4c7e7e919e'
  previous_contract = '0432b529385d20f26d93ca7d75545e8d2490050a94b61286334cd68a52385ca9'
  previous_nogo_review = 'c4bd04d5132e126f7ee79fa1d1b8c4562e004b336395876744a6020109124ca7'
  installed_exe = 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
  installed_manual = '39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3'
  installed_dictionary = '11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0'
  python = '372c2eae555b344520bf147be0096e009069aeca4e7f78d6aecea6d53158056a'
}
function Get-Sha([string]$path) { return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Get-SourceHashes {
  $result = [ordered]@{}
  foreach ($key in $sourcePaths.Keys) {
    if (-not (Test-Path -LiteralPath $sourcePaths[$key])) { throw "source absent: $key" }
    $result[$key] = Get-Sha $sourcePaths[$key]
  }
  if (Test-Path -LiteralPath $approvalPath) { $result['prelaunch_approval'] = Get-Sha $approvalPath }
  return $result
}
$before = Get-SourceHashes
foreach ($key in $expected.Keys) {
  if ($before[$key] -ne $expected[$key]) { throw "frozen source SHA differs: $key" }
}
& $python (Join-Path $case 'build.py') --check | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen builder check failed' }
& $python (Join-Path $case 'check_parent_diff.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'one-cell parent diff failed' }
$parentClosure = Get-Content -LiteralPath $sourcePaths.accepted_closure -Raw | ConvertFrom-Json
if ($parentClosure.run_id -ne 'b03-v102-ssh-20260929-02' -or @($parentClosure.raw.PSObject.Properties).Count -ne 11) { throw 'accepted B03 closure identity/count differs' }
foreach ($artifact in $parentClosure.raw.PSObject.Properties) {
  $path = Join-Path $parentRun $artifact.Name
  if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne $artifact.Value.bytes -or (Get-Sha $path) -ne $artifact.Value.sha256) { throw "accepted B03 raw seal differs: $($artifact.Name)" }
}
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide Issue18 native queue busy' }
  $gui = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -ne 1 -or -not $gui[0].Responding -or ([DateTimeOffset]$gui[0].StartTime.ToUniversalTime()).ToUnixTimeMilliseconds() -ne 1790590196826) { throw 'protected GUI PID/session/start differs' }
  $guiStart = $gui[0].StartTime.ToUniversalTime().ToString('o')
  $sessions = @(qwinsta 2>&1)
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match '^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+1\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)' }).Count -ne 1) { throw 'GUI session not active' }
  function Assert-Gui {
    $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
    if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne 1 -or -not $p[0].Responding -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'protected GUI changed or unresponsive' }
  }
  if (Test-Path -LiteralPath $run) { throw 'run directory appeared during preflight' }
  if ($PreflightOnly) {
    [ordered]@{schema='simlox-b01-var03-task-route-preflight/v1';run_id=$RunId;run_absent=$true;
      ssh_session=0;ssh_ancestors=$ancestors;queue_free=$true;
      gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
      accepted_parent_raw_seals=11;source_hashes=$before;native_process_started=$false} | ConvertTo-Json -Depth 7
    return
  }
  if (-not (Test-Path -LiteralPath $approvalPath)) { throw 'independent prelaunch approval absent' }
  $approval = Get-Content -LiteralPath $approvalPath -Raw | ConvertFrom-Json
  if ($approval.decision -ne 'GO_PRELAUNCH' -or $approval.run_id -ne $RunId -or $approval.contract_sha256 -ne $before.child_contract -or $approval.runner_sha256 -ne $before.runner_script -or $approval.validator_sha256 -ne $before.behavior_validator -or $approval.input_sha256 -ne $before.child_input) { throw 'independent prelaunch approval does not match frozen files' }
  function Run-Command([string]$name,[string]$arguments,[string[]]$required) {
    $step = [ordered]@{name=$name;arguments=$arguments;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;gui_preserved=$false;status='started';error=$null}
    $script:steps += $step
    ConvertTo-Json -InputObject $script:steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
    try {
      Assert-Gui
      $process = Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru
      if (-not $process.WaitForExit(300000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        $process.WaitForExit(10000) | Out-Null
        throw "$name timed out after 300 seconds; only launched child PID $($process.Id) stopped"
      }
      $step.exit_code = $process.ExitCode
      Assert-Gui
      $step.gui_preserved = $true
      if ($step.exit_code -ne 0) { throw "$name exit=$($step.exit_code)" }
      foreach ($file in $required) {
        $path = Join-Path $run $file
        if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -le 4) { throw "$name output $file absent/empty" }
      }
      if ($name -eq 'calc') {
        $log = Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw
        if ($log -notmatch 'Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0' -or @([regex]::Matches($log,'\(warning #108\)')).Count -ne 1 -or @([regex]::Matches($log,'\(warning #126\)')).Count -ne 1 -or @([regex]::Matches($log,'\(warning #\d+\)')).Count -ne 2 -or $log -match '\(error #\d+\)') { throw 'converter diagnostics differ' }
      }
      $step.status = 'completed'
    } catch { $step.status = 'failed'; $step.error = $_.Exception.Message; throw }
    finally {
      $step.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
      ConvertTo-Json -InputObject $script:steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
    }
  }
  New-Item -ItemType Directory -Path (Join-Path $case 'runs') -Force | Out-Null
  New-Item -ItemType Directory -Path $run | Out-Null
  Copy-Item -LiteralPath $sourcePaths.child_input -Destination (Join-Path $run 'input.json')
  if ((Get-Sha (Join-Path $run 'input.json')) -ne $inputSha) { throw 'copied input SHA differs' }
  $commands = @(
    [ordered]@{name='import';arguments=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'input.json'),(Join-Path $run 'model.sxi'),(Join-Path $run 'import.log'))},
    [ordered]@{name='export';arguments=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f (Join-Path $run 'model.sxi'),(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'export.log'))},
    [ordered]@{name='calc';arguments=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f (Join-Path $run 'model.sxi'),(Join-Path $run 'run.log'))},
    [ordered]@{name='jsonreport';arguments=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f (Join-Path $run 'model.sxo'),(Join-Path $run 'report-raw.json'),(Join-Path $run 'report-export.log'))}
  )
  [ordered]@{schema='simlox-b01-var03-task-route-native-candidate/ssh-cli-v1';case_id='B01';variant_id='B01.var03';run_id=$RunId;
    created_utc=(Get-Date).ToUniversalTime().ToString('o');original_run_dir=$run;host_name=$env:COMPUTERNAME;
    input_sha256=$inputSha;contract_sha256=$contractSha;runner_script_sha256=$before.runner_script;
    execution_mode='ssh_cli_v1';session_id=0;ssh_connection_present=$true;ssh_ancestor_names=$ancestors;
    gui=[ordered]@{pid=13340;session_id=1;start_utc=$guiStart;start_unix_ms=1790590196826};
    queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$workingDirectory;
    planned_commands=$commands;source_hashes_before=$before;scope='four_step_native_candidate';publication_state='not_published'} |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps = @()
  $errorText = $null
  try {
    Run-Command 'import' $commands[0].arguments @('model.sxi','import.log')
    Run-Command 'export' $commands[1].arguments @('roundtrip-raw.json','export.log')
    $step = [ordered]@{name='check_import_export';arguments=@((Join-Path $case 'check_roundtrip.py'),$run);started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;gui_preserved=$false;status='started';error=$null}
    $steps += $step
    try {
      Assert-Gui
      & $python (Join-Path $case 'check_roundtrip.py') $run | Set-Content -LiteralPath (Join-Path $run 'roundtrip-validation.json') -Encoding UTF8
      $step.exit_code = $LASTEXITCODE
      Assert-Gui
      $step.gui_preserved = $true
      if ($step.exit_code -ne 0) { throw "roundtrip checker exit=$($step.exit_code)" }
      $step.status = 'completed'
    } catch { $step.status='failed';$step.error=$_.Exception.Message;throw }
    finally {
      $step.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
      ConvertTo-Json -InputObject $steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
    }
    Run-Command 'calc' $commands[2].arguments @('model.sxo','run.log','model.log')
    Run-Command 'jsonreport' $commands[3].arguments @('report-raw.json','report-export.log')
  } catch { $errorText = $_.Exception.Message }
  $after = Get-SourceHashes
  foreach ($key in $before.Keys) { if ($before[$key] -ne $after[$key]) { $errorText = "frozen source changed during native steps: $key" } }
  $raw = @{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File) {
    if ($file.Name -eq 'invocation.json') { continue }
    $raw[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-Sha $file.FullName)}
  }
  [ordered]@{schema='simlox-b01-var03-task-route-native-closure/v1';run_id=$RunId;
    invocation_sha256=(Get-Sha (Join-Path $run 'invocation.json'));source_hashes_before=$before;
    source_hashes_after=$after;raw=$raw;error=$errorText;scope='four_step_native_candidate';publication_state='not_published'} |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
  [ordered]@{run_id=$RunId;run_dir=$run;native_steps='completed';scope='four_step_native_candidate'} | ConvertTo-Json
} catch {
  $failureMessage = $_.Exception.Message
  if (Test-Path -LiteralPath $run) {
    try {
      $preserved = @{}
      foreach ($file in Get-ChildItem -LiteralPath $run -File) {
        if ($file.Name -eq 'failure-seal.json') { continue }
        $preserved[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-Sha $file.FullName)}
      }
      [ordered]@{schema='simlox-b01-var03-task-route-failure-seal/v1';run_id=$RunId;error=$failureMessage;
        files=$preserved;publication_state='excluded'} | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath (Join-Path $run 'failure-seal.json') -Encoding UTF8
    } catch { Write-Warning "failure seal write failed: $($_.Exception.Message)" }
  }
  throw $failureMessage
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

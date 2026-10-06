param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
  [switch]$PreflightOnly
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$root = Split-Path $case -Parent
$run = Join-Path (Join-Path $case 'runs') $RunId
$parent = Join-Path $root 'B04-var05-turnround-breakdown-v0.1.0'
$parentRun = Join-Path $parent 'runs\b04-var05-turnbreak-v010-ssh-20261006-01'
$prereq = Join-Path $root 'C01-personnel-capacity-v1.0.2'
$prereqRun = 'C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support\C01-personnel-capacity-v1.0.2\runs\c01-v102-cap2-ssh-20260929-05'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary = 'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$approvalPath = Join-Path $case 'review\independent-prelaunch-go.json'
$inputSha = '0d799bc6b2d4f8184db0bc33ddbffcaa51a822478b746fab3d4be9d942ee34d5'
$contractSha = 'eddc9b1221ac6f0c1acb4c55764bb218c61b251ca58435fb8f2f14efc3b8d49d'
if ($RunId -ne 'b04-var02-turn-resource-v011-ssh-20261006-01') { throw 'unreviewed run identity' }
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
  contract_review = (Join-Path $case 'review\independent-contract-go-2026-10-07.md')
  builder = (Join-Path $case 'build.py')
  parent_diff_checker = (Join-Path $case 'check_parent_diff.py')
  roundtrip_checker = (Join-Path $case 'check_roundtrip.py')
  shared_parser = (Join-Path $root 'tools\validate_native.py')
  behavior_validator = (Join-Path $case 'validate_native_cli.py')
  runner_script = $PSCommandPath
  accepted_input = (Join-Path $parent 'native-input.json')
  accepted_contract = (Join-Path $parent 'contract.json')
  accepted_signoff = (Join-Path $parent 'cli-scope-signoff-2026-10-06.md')
  accepted_closure = (Join-Path $parentRun 'closure.json')
  accepted_report = (Join-Path $parentRun 'report-raw.json')
  prereq_input = (Join-Path $prereq 'inputs\capacity-2.json')
  prereq_closure = (Join-Path $prereqRun 'closure.json')
  installed_exe = $exe
  installed_manual = $manual
  installed_dictionary = $dictionary
  python = $python
}
$expected = @{
  child_input = $inputSha
  child_contract = $contractSha
  contract_review = 'cfb0ba4ee149e9d98af0988eeb2602ecc854be48523034f911b549ef0b542597'
  builder = 'd803c7c6cf9399aff49edf4654aeccfa6558b1c6402b176d7a3756993f84c3b7'
  parent_diff_checker = 'f33ed7786af531251e900e59abb25c2f15e965b1183a580b590ba91814a54a2c'
  roundtrip_checker = 'ef1fe32a4c3e56db08b8cbfcfd4639d4efee693fc0f0584ae05ec1da92778543'
  shared_parser = '43b42fbc5f6d2b9ecbeb82b1419224d6a99025c1be5c600dd959f77d362b6354'
  behavior_validator = 'fabc0b7f2185690e1a617a49baec3dc4f275be4ddbb371cd8ee11e9d8c615b08'
  accepted_input = '965a3acc431696e56b760b07323e4cf11cb571e030885fff708787ce84f3e42f'
  accepted_contract = '5292459de185e04ef445ff89e4e20cb1c8d9148151f767340b59893d089d3020'
  accepted_signoff = 'd875f3dd1d118f8da6d8a49840a73fb706a3fc777c2287b3dfae58242a10043d'
  accepted_closure = '58a4838596f96e07d5d20fff3cc4e02a7d3ef07f539d61f3a5c5caf0ca84b545'
  accepted_report = 'df1c6055ce7cd32dea0e02112ab752bc34ec2484311e7d0baa44b04910a1c87a'
  prereq_input = 'a0d81fcfd065aa393b7ea9dace2b089e4779077e99cb242a2eae0299318c216c'
  prereq_closure = '770537c9097ba24fbec533d5c6f1eafa29153c18bde63cd0b1bc621a65c55163'
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
function Check-RawClosure([string]$path,[string]$directory,[string]$runId,[int]$count) {
  $closure = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
  if ($closure.run_id -ne $runId -or @($closure.raw.PSObject.Properties).Count -ne $count) { throw "accepted raw closure identity/count differs: $runId" }
  foreach ($artifact in $closure.raw.PSObject.Properties) {
    $file = Join-Path $directory $artifact.Name
    if (-not (Test-Path -LiteralPath $file) -or (Get-Item -LiteralPath $file).Length -ne $artifact.Value.bytes -or (Get-Sha $file) -ne $artifact.Value.sha256) { throw "accepted raw seal differs: $runId/$($artifact.Name)" }
  }
}
$before = Get-SourceHashes
foreach ($key in $expected.Keys) { if ($before[$key] -ne $expected[$key]) { throw "frozen source SHA differs: $key" } }
& $python (Join-Path $case 'build.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen builder check failed' }
& $python (Join-Path $case 'check_parent_diff.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'parent diff check failed' }
Check-RawClosure $sourcePaths.accepted_closure $parentRun 'b04-var05-turnbreak-v010-ssh-20261006-01' 13
Check-RawClosure $sourcePaths.prereq_closure $prereqRun 'c01-v102-cap2-ssh-20260929-05' 11
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
    [ordered]@{schema='simlox-b04-var02-v011-preflight/v1';run_id=$RunId;run_absent=$true;ssh_session=0;
      ssh_ancestors=$ancestors;queue_free=$true;gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
      accepted_b04_var05_raw_seals=13;accepted_c01_raw_seals=11;source_hashes=$before;native_process_started=$false} | ConvertTo-Json -Depth 7
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
      $step.status = 'completed'
    } catch { $step.status='failed';$step.error=$_.Exception.Message;throw }
    finally { $step.completed_utc = (Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $script:steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
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
  [ordered]@{schema='simlox-b04-var02-v011-native-candidate/ssh-cli-v1';case_id='B04';variant_id='B04.var02';run_id=$RunId;
    created_utc=(Get-Date).ToUniversalTime().ToString('o');original_run_dir=$run;host_name=$env:COMPUTERNAME;
    input_sha256=$inputSha;contract_sha256=$contractSha;runner_script_sha256=$before.runner_script;
    execution_mode='ssh_cli_v1';session_id=0;ssh_connection_present=$true;ssh_ancestor_names=$ancestors;
    gui=[ordered]@{pid=13340;session_id=1;start_utc=$guiStart;start_unix_ms=1790590196826};
    queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$workingDirectory;
    planned_commands=$commands;source_hashes_before=$before;scope='behavior_candidate';publication_state='not_published'} |
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
    finally { $step.completed_utc = (Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
    Run-Command 'calc' $commands[2].arguments @('model.sxo','model.log','run.log')
    $calcLog = Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw
    if ($calcLog -notmatch 'Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0') { throw 'zero-error converter gate failed' }
    Run-Command 'jsonreport' $commands[3].arguments @('report-raw.json','report-export.log')
    $step = [ordered]@{name='check_behavior';arguments=@((Join-Path $case 'validate_native_cli.py'),$run);started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;gui_preserved=$false;status='started';error=$null}
    $steps += $step
    try {
      Assert-Gui
      & $python (Join-Path $case 'validate_native_cli.py') $run | Set-Content -LiteralPath (Join-Path $run 'author-validation.json') -Encoding UTF8
      $step.exit_code = $LASTEXITCODE
      Assert-Gui
      $step.gui_preserved = $true
      if ($step.exit_code -ne 0) { throw "author behavior checker exit=$($step.exit_code)" }
      $step.status = 'completed'
    } catch { $step.status='failed';$step.error=$_.Exception.Message;throw }
    finally { $step.completed_utc = (Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
  } catch { $errorText = $_.Exception.Message }
  $after = Get-SourceHashes
  foreach ($key in $before.Keys) { if ($before[$key] -ne $after[$key]) { $errorText = "frozen source changed during native steps: $key" } }
  $raw = @{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File) {
    if ($file.Name -eq 'invocation.json') { continue }
    $raw[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-Sha $file.FullName)}
  }
  [ordered]@{schema='simlox-b04-var02-v011-native-closure/v1';run_id=$RunId;
    invocation_sha256=(Get-Sha (Join-Path $run 'invocation.json'));source_hashes_before=$before;
    source_hashes_after=$after;raw=$raw;error=$errorText;scope='behavior_candidate';publication_state='not_published'} |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
  [ordered]@{run_id=$RunId;run_dir=$run;native_steps='completed';scope='behavior_candidate'} | ConvertTo-Json
} catch {
  $failureMessage = $_.Exception.Message
  if (Test-Path -LiteralPath $run) {
    try {
      $preserved = @{}
      foreach ($file in Get-ChildItem -LiteralPath $run -File) {
        if ($file.Name -eq 'failure-seal.json') { continue }
        $preserved[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-Sha $file.FullName)}
      }
      [ordered]@{schema='simlox-b04-var02-v011-failure-seal/v1';run_id=$RunId;error=$failureMessage;
        files=$preserved;publication_state='excluded'} | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath (Join-Path $run 'failure-seal.json') -Encoding UTF8
    } catch { Write-Warning "failure seal write failed: $($_.Exception.Message)" }
  }
  throw $failureMessage
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
  [switch]$PreflightOnly
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$root = Split-Path $case -Parent
$run = Join-Path (Join-Path $case 'runs') $RunId
$parent = Join-Path $root 'A03-two-aircraft-formation-v1.0.1'
$parentRun = 'C:\Users\user\Documents\Codex\2026-09-28\simlox-issue18-ssh-current\cases\simlox-air-support\A03-two-aircraft-formation-v1.0.1\runs\a03-v101-ssh-gui-20260929-01'
$a02 = Join-Path $root 'A02-single-aircraft-repeated-missions'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary = 'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$approvalPath = Join-Path $case 'review\independent-prelaunch-go.json'
$inputSha = '6fc81a5a5ce9304c007a2087a0116cb585bf3fe70312649937e43d0576be0e71'
$contractSha = 'a466a9faab28b518e037f56b90be7a8c1cfce7be99b1fb542c6de3828b17994e'
if ($RunId -ne 'a03-var01-three-avail-v010-ssh-20261006-01') { throw 'unreviewed run identity' }
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
  accepted_signoff = (Join-Path $parent 'cli-scope-signoff-2026-09-29.md')
  accepted_verdict = (Join-Path $parent 'review\independent-readonly-2026-09-29.json')
  accepted_closure = (Join-Path $parentRun 'closure.json')
  a02_input = (Join-Path $a02 'native-input.json')
  a02_signoff = (Join-Path $a02 'cli-scope-signoff-2026-09-29.md')
  installed_exe = $exe
  installed_manual = $manual
  installed_dictionary = $dictionary
  python = $python
}
$expected = @{
  child_input = $inputSha
  child_contract = $contractSha
  contract_review = 'cfe12c5cf2575180886ad73801bfde8f0531e1505773b47d2e79e47bfaf1c9ef'
  builder = '1b8203c071bcae8894f4643fcd4cd8969a25742ecf29ba82d90d10401502c0de'
  parent_diff_checker = '74b6c98256a070973d0d37b00bc8bbf725b3ecb5055cf01ab7697e3e0b4dfdab'
  roundtrip_checker = '757fbb4da0abf993ce62fac5df0a9ee4a8bdf9ab54a0e5dc5fdc47f29adaa9f0'
  shared_parser = '43b42fbc5f6d2b9ecbeb82b1419224d6a99025c1be5c600dd959f77d362b6354'
  behavior_validator = 'a1d6ff3a63fcf580921b74f9e85dec2f25b0d80377472f5bcf190374795b6ebb'
  accepted_input = 'd7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4'
  accepted_contract = '123b5391d0b17fdd0b7d61088c883e7cfb891892fe89c7cb85b27e30868ea34d'
  accepted_signoff = '6c8d3998f20e216d0403b807866fcbe306f68ebc6f376693334435e808747b2b'
  accepted_verdict = '646e2076eb03565b4fb390b98d8651c5c1403380a28a9d5b99bb9a06a37d9282'
  accepted_closure = 'a3b4a2739b5b098c956aa19428cf997b2079aab858e22fb5ea9c4486a4209edd'
  a02_input = '84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8'
  a02_signoff = '608eef828a65ef7a8c738a3ec227b890421c29248ee8addd9e992a4c7e7e919e'
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
& $python (Join-Path $case 'build.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen builder check failed' }
& $python (Join-Path $case 'check_parent_diff.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'one-cell parent diff failed' }
$sealed = Get-Content -LiteralPath $sourcePaths.accepted_closure -Raw | ConvertFrom-Json
if ($sealed.run_id -ne 'a03-v101-ssh-gui-20260929-01' -or $sealed.error -or @($sealed.raw.PSObject.Properties).Count -ne 11) { throw 'accepted A03 closure identity/count differs' }
foreach ($artifact in $sealed.raw.PSObject.Properties) {
  $path = Join-Path $parentRun $artifact.Name
  if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne $artifact.Value.bytes -or (Get-Sha $path) -ne $artifact.Value.sha256) { throw "accepted A03 raw seal differs: $($artifact.Name)" }
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
    [ordered]@{schema='simlox-a03-var01-preflight/v1';run_id=$RunId;run_absent=$true;
      ssh_session=0;ssh_ancestors=$ancestors;queue_free=$true;
      gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
      accepted_a03_parent_raw_seals=11;source_hashes=$before;native_process_started=$false} | ConvertTo-Json -Depth 7
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
  [ordered]@{schema='simlox-a03-var01-native-candidate/ssh-cli-v1';case_id='A03';variant_id='A03.var01';run_id=$RunId;
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
  [ordered]@{schema='simlox-a03-var01-native-closure/v1';run_id=$RunId;
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
      [ordered]@{schema='simlox-a03-var01-failure-seal/v1';run_id=$RunId;error=$failureMessage;
        files=$preserved;publication_state='excluded'} | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath (Join-Path $run 'failure-seal.json') -Encoding UTF8
    } catch { Write-Warning "failure seal write failed: $($_.Exception.Message)" }
  }
  throw $failureMessage
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

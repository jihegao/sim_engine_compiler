param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
  [switch]$PreflightOnly
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$root = Split-Path $case -Parent
$run = Join-Path (Join-Path $case 'runs') $RunId
$parent = Join-Path $root 'A02-single-aircraft-repeated-missions'
$prereq = Join-Path $root 'A01-single-aircraft-single-mission'
$parentRun = 'C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A02\a02-bound-final-20260927-03'
$parentReplay = 'C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A02\a02-bound-replay-20260927-04'
$prereqFinal = 'C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A01\a01-bound-final-20260927-03'
$prereqReplay = 'C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A01\a01-bound-replay-20260927-04'
$analoguePackage = Join-Path $root 'A02-var01-insufficient-gap-v0.1.1'
$analogueRun = Join-Path $analoguePackage 'runs\a02-var01-insufficient-gap-v011-ssh-20261006-01'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary = 'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$approvalPath = Join-Path $case 'review\independent-prelaunch-go.json'
$inputSha = '856b7e60086b2b2983245a117601bde35392801fea97f109164fb4364bec8a76'
$contractSha = 'e9792037600763ee8309b77bb6622a975830ab80332652ad026e240ed4985d47'
if ($RunId -ne 'a02-var03-same-time-v010-ssh-20261006-01') { throw 'unreviewed run identity' }
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
  analogue_input = (Join-Path $analoguePackage 'native-input.json')
  analogue_contract = (Join-Path $analoguePackage 'contract.json')
  analogue_signoff = (Join-Path $analoguePackage 'cli-scope-signoff-2026-10-06.md')
  analogue_index = (Join-Path $analoguePackage 'evidence-index.json')
  analogue_verdict = (Join-Path $analoguePackage 'review\independent-verdict.json')
  analogue_closure = (Join-Path $analogueRun 'closure.json')
  analogue_log = (Join-Path $analogueRun 'model.log')
  analogue_report = (Join-Path $analogueRun 'report-raw.json')
  negative_checker = (Join-Path $case 'check_negative_control.py')
  negative_control = (Join-Path $case 'review\negative-control-accepted-parent-and-analogue.json')
  builder = (Join-Path $case 'build.py')
  parent_diff = (Join-Path $case 'check_parent_diff.py')
  roundtrip_checker = (Join-Path $case 'check_roundtrip.py')
  behavior_validator = (Join-Path $case 'validate_native_cli.py')
  runner_script = $PSCommandPath
  accepted_input = (Join-Path $parent 'native-input.json')
  accepted_contract = (Join-Path $parent 'contract.json')
  accepted_signoff = (Join-Path $parent 'cli-scope-signoff-2026-09-29.md')
  accepted_index = (Join-Path $parent 'evidence-index.json')
  accepted_final_closure = (Join-Path $parentRun 'closure.json')
  accepted_replay_closure = (Join-Path $parentReplay 'closure.json')
  prereq_input = (Join-Path $prereq 'native-input.json')
  prereq_contract = (Join-Path $prereq 'contract.json')
  prereq_signoff = (Join-Path $prereq 'cli-scope-signoff-2026-09-29.md')
  prereq_index = (Join-Path $prereq 'evidence-index.json')
  prereq_final_closure = (Join-Path $prereqFinal 'closure.json')
  prereq_replay_closure = (Join-Path $prereqReplay 'closure.json')
  installed_manual = $manual
  installed_dictionary = $dictionary
  installed_exe = $exe
  python = $python
}
$expected = @{
  child_input = $inputSha
  child_contract = $contractSha
  contract_review = '3dd392712a0e2a9882d4ea6ac220f3e7011eedfa3b3240e6ae6d3b7c1d708f1b'
  analogue_input = 'df7d693e7364c50d489723c2d4c336c1225959e1e03cfb6535f82d9cf32a2109'
  analogue_contract = 'f674de2448d4c97e909da95c1c0a3c9ffbea743da19bb0042d16ba6d5137a6d5'
  analogue_signoff = '29f87822b829995d547fc81f02fb558189d5214c76d844cfa06ede5e5a6bf98c'
  analogue_index = 'd0f464c7aaf14c86fbcae8ddecda4149136af20b978467dd9b8a93fa0445f149'
  analogue_verdict = 'fa667cfc7c6f2c0ad4409240780fe3e5c54d0f02c2115fd7b12f109289710fe4'
  analogue_closure = 'fff531321e18b8c8074ca172da5b83c729d7aa356484cbd2c00e3d05305546b1'
  analogue_log = 'ae99693f61618e10212b414855aee1995f3744b73f8a3960d8955ebbd5ab3514'
  analogue_report = '34c89ae5ffb33e25d853ea57131b658d117b5212d8496fa6e61c48e43c5c0e8d'
  negative_checker = '11eb9612c5578c7474ddc608bbee3104a2e77236ceee7eab748ad2be6411ddfd'
  negative_control = '36b261e476e439900a02d3ee80a6a21944bfa40ba07b020cd8f6ba38a4f2285e'
  builder = 'e06e951e8f07cf010f93dd018f04c41e7e8e76ea96fcd64f180efa7e0bcf6887'
  parent_diff = '6491fd5f0cc1b856a316fb7da6c508495fb9e1c33c95e4bf75d1d71233df90d8'
  roundtrip_checker = 'b50084ff9d9c583d476d884e04a1b877d94a0f4e95f0ee489cd14f3c35e727f9'
  behavior_validator = 'e1d23bba6dee732a49fe819e2e863f49b59fc31df81043b0762aef5694f88b2d'
  accepted_input = '84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8'
  accepted_contract = 'f192c22de44ec20cf8581e2652ce8b4a44fc315acb7998624be340cb5a42a465'
  accepted_signoff = '608eef828a65ef7a8c738a3ec227b890421c29248ee8addd9e992a4c7e7e919e'
  accepted_index = 'b584816ca459c75bd5de160eb44b7b458c0dbe1b478c56142c44a3283732041d'
  accepted_final_closure = 'fc0cc2d0578d2e8d126e79886ab2ba72238a725aea86c361ede6d48dadc6a69a'
  accepted_replay_closure = '9a44bc9f5d52cfd2178545315b6cd9b380585e98c36502025b329e380f1909d1'
  prereq_input = '8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7'
  prereq_contract = '29d81aeadc5b138b07a3e6242fec8df74a768998c71d3ee0e5e4ca0bf45c7cb6'
  prereq_signoff = '20ca6217068b2c6b998e70f26a82b065ebf6a15e555769c176baee204c137afa'
  prereq_index = '2fe2383e513b0e59c581d5e7b48ec8da000a674a9f41e257b0e4f91836deb880'
  prereq_final_closure = '7e253f9acdeed55197e191530f7e9ad8d88abe387326fd7b4c5152da3529288e'
  prereq_replay_closure = '3781103d253f08c6d3f8f84572877f6b65319a18c10a9e40736e608f829811ee'
  installed_manual = '39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3'
  installed_dictionary = '11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0'
  installed_exe = 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
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
if ($LASTEXITCODE -ne 0) { throw 'one-cell parent diff check failed' }
function Assert-IndexedRaw([string]$indexPath,[string[]]$runIds,[string]$label) {
  $index = Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json
  if (@($index.runs).Count -ne 2) { throw "$label index must bind final and replay" }
  foreach ($expectedRunId in $runIds) {
    if (@($index.runs | Where-Object { $_.run_id -eq $expectedRunId }).Count -ne 1) { throw "$label missing/duplicate indexed run: $expectedRunId" }
  }
  foreach ($entry in @($index.runs)) {
    if ($entry.run_id -notin $runIds -or @($entry.artifacts.PSObject.Properties).Count -ne 17) { throw "$label indexed run identity/count differs" }
    foreach ($artifact in $entry.artifacts.PSObject.Properties) {
      $path = $artifact.Value.path
      if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne $artifact.Value.bytes -or (Get-Sha $path) -ne $artifact.Value.sha256) { throw "$label raw seal differs: $($entry.run_id)/$($artifact.Name)" }
    }
  }
}
Assert-IndexedRaw $sourcePaths.accepted_index @('a02-bound-final-20260927-03','a02-bound-replay-20260927-04') 'accepted A02'
Assert-IndexedRaw $sourcePaths.prereq_index @('a01-bound-final-20260927-03','a01-bound-replay-20260927-04') 'accepted A01'
$analogueClosure = Get-Content -LiteralPath $sourcePaths.analogue_closure -Raw | ConvertFrom-Json
if ($analogueClosure.run_id -ne 'a02-var01-insufficient-gap-v011-ssh-20261006-01' -or $analogueClosure.error -or @($analogueClosure.raw.PSObject.Properties).Count -ne 12) { throw 'accepted A02 cancellation analogue closure identity differs' }
foreach ($artifact in $analogueClosure.raw.PSObject.Properties) {
  $path = Join-Path $analogueRun $artifact.Name
  if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne $artifact.Value.bytes -or (Get-Sha $path) -ne $artifact.Value.sha256) { throw "accepted A02 cancellation analogue raw seal differs: $($artifact.Name)" }
}
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide Issue18 native queue busy' }
  $gui = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -ne 1 -or -not $gui[0].Responding -or ([DateTimeOffset]$gui[0].StartTime.ToUniversalTime()).ToUnixTimeMilliseconds() -ne 1790590196826) { throw 'protected GUI PID/session/start identity differs' }
  $guiStart = $gui[0].StartTime.ToUniversalTime().ToString('o')
  $sessions = @(qwinsta 2>&1)
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match '^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+1\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)' }).Count -ne 1) { throw 'GUI session not active' }
  function Assert-Gui {
    $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
    if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne 1 -or -not $p[0].Responding -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'protected GUI changed or unresponsive' }
  }
  if (Test-Path -LiteralPath $run) { throw 'run directory appeared during preflight' }
  if ($PreflightOnly) {
    [ordered]@{ schema='simlox-a02-var03-same-time-v010-preflight/v1'; run_id=$RunId; run_absent=$true;
      ssh_session=0; ssh_ancestors=$ancestors; queue_free=$true;
      gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
      accepted_parent_raw_seals=68; accepted_analogue_raw_seals=12; source_hashes=$before; native_process_started=$false } | ConvertTo-Json -Depth 7
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
    } catch {
      $step.status = 'failed'; $step.error = $_.Exception.Message
      throw
    } finally {
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
  [ordered]@{schema='simlox-a02-var03-same-time-v010-native-candidate/ssh-cli-v1';case_id='A02';variant_id='A02.var03';run_id=$RunId;
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
    } catch { $step.status='failed';$step.error=$_.Exception.Message;throw } finally {
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
  [ordered]@{schema='simlox-a02-var03-same-time-v010-native-closure/v1';run_id=$RunId;
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
      [ordered]@{schema='simlox-a02-var03-same-time-v010-failure-seal/v1';run_id=$RunId;error=$failureMessage;
        files=$preserved;publication_state='excluded'} | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath (Join-Path $run 'failure-seal.json') -Encoding UTF8
    } catch { Write-Warning "failure seal write failed: $($_.Exception.Message)" }
  }
  throw $failureMessage
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

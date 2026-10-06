param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
  [switch]$PreflightOnly
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$root = Split-Path $case -Parent
$run = Join-Path (Join-Path $case 'runs') $RunId
$parent = Join-Path $root 'A01-single-aircraft-single-mission'
$sibling = Join-Path $root 'A01-var01-zero-outbound-v0.1.0'
$siblingRun = Join-Path $sibling 'runs\a01-var01-tfout0-v010-ssh-20261006-01'
$sibling2 = Join-Path $root 'A01-var01-sum-one-v0.1.0'
$sibling2Run = Join-Path $sibling2 'runs\a01-var01-sum1-v010-ssh-20261006-01'
$parentRun = 'C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A01\a01-bound-final-20260927-03'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$approvalPath = Join-Path $case 'review\independent-prelaunch-go.json'
$inputSha = '66f2c6fc9d7e4438514f4965c968e0bc3d11db824fd5682f06d1e7362a1346ef'
$contractSha = '15afed5c5c0b344ecbbfb419a0c326dc4c5a0ed3ff8e4d180ca543b47079c987'
if ($RunId -ne 'a01-var01-tfret0-v010-ssh-20261006-01') { throw 'unreviewed run identity' }
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
  negative_checker = (Join-Path $case 'check_negative_control.py')
  negative_control = (Join-Path $case 'review\negative-control-accepted-parent.json')
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
  accepted_replay_closure = 'C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A01\a01-bound-replay-20260927-04\closure.json'
  sibling_input = (Join-Path $sibling 'native-input.json')
  sibling_signoff = (Join-Path $sibling 'cli-scope-signoff-2026-10-06.md')
  sibling_index = (Join-Path $sibling 'evidence-index.json')
  sibling_closure = (Join-Path $siblingRun 'closure.json')
  sibling2_input = (Join-Path $sibling2 'native-input.json')
  sibling2_signoff = (Join-Path $sibling2 'cli-scope-signoff-2026-10-06.md')
  sibling2_index = (Join-Path $sibling2 'evidence-index.json')
  sibling2_closure = (Join-Path $sibling2Run 'closure.json')
  installed_manual = $manual
  installed_exe = $exe
  python = $python
}
$expected = @{
  child_input = $inputSha
  child_contract = $contractSha
  contract_review = '2ce4709094ddbe56f9553b7af3dcb1b637ee37e0e907430f0560eaca2413efdc'
  negative_checker = '3b744bfdd04f505c1f52c3771032a2141c098af80619b2a76655cc58f930f7d7'
  negative_control = '76e47156e92945704211d081102dce0c410ff2d7014db3fb28191130005136ec'
  builder = '76cc6d2bbe7849ff275f227ec349e6c2a74b143680ca10ea12e8f95ae2265159'
  parent_diff = '7a9169a77fb27763e210df1d90d1ebb26648be695f349d2639cc8785a2b8dfa4'
  roundtrip_checker = 'ae0a544fd6f2bd42ac3a172873dd9009e66f825995c56364b9334da3ec430b30'
  behavior_validator = '3c297af2a348cadc30d6393523b3b9629805c8f81854056cdfb8f6ba18d725c3'
  accepted_input = '8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7'
  accepted_contract = '29d81aeadc5b138b07a3e6242fec8df74a768998c71d3ee0e5e4ca0bf45c7cb6'
  accepted_signoff = '20ca6217068b2c6b998e70f26a82b065ebf6a15e555769c176baee204c137afa'
  accepted_index = '2fe2383e513b0e59c581d5e7b48ec8da000a674a9f41e257b0e4f91836deb880'
  accepted_final_closure = '7e253f9acdeed55197e191530f7e9ad8d88abe387326fd7b4c5152da3529288e'
  accepted_replay_closure = '3781103d253f08c6d3f8f84572877f6b65319a18c10a9e40736e608f829811ee'
  sibling_input = 'ac0c134a34362c2cec6ec6c51a90b0f81a7d21b229e8ec76a2595a818d14e3ea'
  sibling_signoff = '26d2b99528992c630ea7c1fc875be161f63ed1d95dfc750196f6ddcbb73c3006'
  sibling_index = '0372f51f8dfe83f43e1b91ffb3f92ca2fc887fcbbdb20725ebb18ede51b6d91f'
  sibling_closure = 'ea378b70e1e5af5f37b47dc2dd20a4318943fdb24a1608745eccf549eda809af'
  sibling2_input = '242d83ba901e7f64dc8a0ccefd4f5a405a51ede86359e240d4abb12bf543b1f9'
  sibling2_signoff = '3dbc766842d988f03b6973337d0437db671c1a5e2a15ce5c5e18e5c7a3d97f51'
  sibling2_index = '4ede9d1078be7c3e64d47def072615865914ed9cea9ce0cd1a52e581b259acf0'
  sibling2_closure = '3cf082ca278f91d4afb0b63b0a4bbc2de560e62c6574966e0fb67a62e4500b4e'
  installed_manual = '39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3'
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
$index = Get-Content -LiteralPath $sourcePaths.accepted_index -Raw | ConvertFrom-Json
foreach ($entry in @($index.runs)) {
  if ($entry.run_id -notin @('a01-bound-final-20260927-03','a01-bound-replay-20260927-04')) { continue }
  foreach ($artifact in $entry.artifacts.PSObject.Properties) {
    $path = $artifact.Value.path
    if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne $artifact.Value.bytes -or (Get-Sha $path) -ne $artifact.Value.sha256) { throw "accepted A01 raw seal differs: $($entry.run_id)/$($artifact.Name)" }
  }
}
if (@($index.runs).Count -ne 2) { throw 'accepted A01 index must bind final and replay' }
$siblingClosure = Get-Content -LiteralPath $sourcePaths.sibling_closure -Raw | ConvertFrom-Json
if ($siblingClosure.run_id -ne 'a01-var01-tfout0-v010-ssh-20261006-01' -or $siblingClosure.error -or @($siblingClosure.raw.PSObject.Properties).Count -ne 12) { throw 'published zero sibling closure differs' }
foreach ($artifact in $siblingClosure.raw.PSObject.Properties) {
  $path = Join-Path $siblingRun $artifact.Name
  if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne $artifact.Value.bytes -or (Get-Sha $path) -ne $artifact.Value.sha256) { throw "published zero sibling raw seal differs: $($artifact.Name)" }
}
$sibling2Closure = Get-Content -LiteralPath $sourcePaths.sibling2_closure -Raw | ConvertFrom-Json
if ($sibling2Closure.run_id -ne 'a01-var01-sum1-v010-ssh-20261006-01' -or $sibling2Closure.error -or @($sibling2Closure.raw.PSObject.Properties).Count -ne 12) { throw 'published sum-one sibling closure differs' }
foreach ($artifact in $sibling2Closure.raw.PSObject.Properties) {
  $path = Join-Path $sibling2Run $artifact.Name
  if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne $artifact.Value.bytes -or (Get-Sha $path) -ne $artifact.Value.sha256) { throw "published sum-one sibling raw seal differs: $($artifact.Name)" }
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
    [ordered]@{ schema='simlox-a01-var01-zero-return-v010-preflight/v1'; run_id=$RunId; run_absent=$true;
      ssh_session=0; ssh_ancestors=$ancestors; queue_free=$true;
      gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
      accepted_raw_seals=58; source_hashes=$before; native_process_started=$false } | ConvertTo-Json -Depth 7
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
  [ordered]@{schema='simlox-a01-var01-zero-return-v010-native-candidate/ssh-cli-v1';case_id='A01';variant_id='A01.var01';run_id=$RunId;
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
  [ordered]@{schema='simlox-a01-var01-zero-return-v010-native-closure/v1';run_id=$RunId;
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
      [ordered]@{schema='simlox-a01-var01-zero-return-v010-failure-seal/v1';run_id=$RunId;error=$failureMessage;
        files=$preserved;publication_state='excluded'} | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath (Join-Path $run 'failure-seal.json') -Encoding UTF8
    } catch { Write-Warning "failure seal write failed: $($_.Exception.Message)" }
  }
  throw $failureMessage
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

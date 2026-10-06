param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
  [switch]$PreflightOnly
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$root = Split-Path $case -Parent
$run = Join-Path (Join-Path $case 'runs') $RunId
$parent = Join-Path $root 'A03-var01-one-of-two-v0.1.0'
$parentRun = Join-Path $parent 'runs\a03-var01-one-of-two-v010-ssh-20261006-01'
$diagnostic = Join-Path $root 'A03-var01-zero-available-v0.1.0'
$diagnosticRun = Join-Path $diagnostic 'runs\a03-var01-zero-v010-ssh-20261006-01'
$diagnosticV011 = Join-Path $root 'A03-var01-zero-available-v0.1.1'
$diagnosticV011Run = Join-Path $diagnosticV011 'runs\a03-var01-zero-v011-ssh-20261006-01'
$a03 = Join-Path $root 'A03-two-aircraft-formation-v1.0.1'
$a02 = Join-Path $root 'A02-single-aircraft-repeated-missions'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary = 'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$approvalPath = Join-Path $case 'review\independent-prelaunch-go.json'
$inputSha = '567c66db4faa12ab6e82ea72613f6b2d293ab608ebaed6a79f7daf2996e25f9b'
$contractSha = 'e0697933960d2f0da96de0c85d8c7d8bc752d1dfdbcfb23d06760747589f9c22'
if ($RunId -ne 'a03-var01-zero-v012-ssh-20261006-01') { throw 'unreviewed run identity' }
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
  accepted_signoff = (Join-Path $parent 'cli-scope-signoff-2026-10-06.md')
  accepted_index = (Join-Path $parent 'evidence-index.json')
  accepted_verdict = (Join-Path $parent 'review\independent-verdict.json')
  accepted_closure = (Join-Path $parentRun 'closure.json')
  diagnostic_input = (Join-Path $diagnostic 'native-input.json')
  diagnostic_contract = (Join-Path $diagnostic 'contract.json')
  diagnostic_runner = (Join-Path $diagnostic 'run_native_ssh.ps1')
  diagnostic_closure = (Join-Path $diagnosticRun 'closure.json')
  diagnostic_failure_seal = (Join-Path $diagnosticRun 'failure-seal.json')
  diagnostic_run_log = (Join-Path $diagnosticRun 'run.log')
  diagnostic_model_log = (Join-Path $diagnosticRun 'model.log')
  diagnostic_v011_input = (Join-Path $diagnosticV011 'native-input.json')
  diagnostic_v011_contract = (Join-Path $diagnosticV011 'contract.json')
  diagnostic_v011_runner = (Join-Path $diagnosticV011 'run_native_ssh.ps1')
  diagnostic_v011_validator = (Join-Path $diagnosticV011 'validate_native_cli.py')
  diagnostic_v011_closure = (Join-Path $diagnosticV011Run 'closure.json')
  diagnostic_v011_report = (Join-Path $diagnosticV011Run 'report-raw.json')
  diagnostic_v011_author = (Join-Path $diagnosticV011 'review\author-validation.json')
  diagnostic_v011_review = (Join-Path $diagnosticV011 'review\independent-diagnostic-2026-10-06.md')
  a03_input = (Join-Path $a03 'native-input.json')
  a03_signoff = (Join-Path $a03 'cli-scope-signoff-2026-09-29.md')
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
  contract_review = 'b4a3d880cca94f5d2a31b53d75b8e0b21ace351c12f0013c1ce76b04bf8f3ed6'
  builder = 'dbd9315901b0f8ab6fd8faa4748b3a9bd9c05714166bd48749cc8173d216a4b9'
  parent_diff_checker = '4935143d667c444856334b6d27ef9953ebe2bdaf493ef54a1fd0fba436f569ed'
  roundtrip_checker = '5f5b61766d05810bca5172f4ffbb3faa3986ce995e06c9e369a82cf68b9dcc49'
  shared_parser = '43b42fbc5f6d2b9ecbeb82b1419224d6a99025c1be5c600dd959f77d362b6354'
  behavior_validator = '2486b18e417f8c904f783403c0faf38cb3608f1bf71d04563bb6e3781b83a03f'
  accepted_input = '6b5807f42006a85f63777529d258ea1b563e5747f527821ab704f05f1d696709'
  accepted_contract = '4dee8c85767195aef9e382be9aaa0c9169236873408698863227f6e883d8728c'
  accepted_signoff = 'ee68e7d0aae2dfa343f3e6dc9ecac4fce238c741a41b6a0564e358d5bb9d14bc'
  accepted_index = '5e91871b915dde1b9c7a3584384a3c3764f6667f7fada19d23b1a9ce79086a3f'
  accepted_verdict = '26daffd726ad21c802df65cdd3774e348498f40b36715e9b1c3e8cf2081c21d3'
  accepted_closure = '56b4e09312b3df67495d4961e296fea0c3e0f5f01413c5e1f2ae3fb243ac1772'
  diagnostic_input = '567c66db4faa12ab6e82ea72613f6b2d293ab608ebaed6a79f7daf2996e25f9b'
  diagnostic_contract = 'f344c70fba41bf34103ad391f85068568316d8b4238889f531742074a4687238'
  diagnostic_runner = 'e8103dab4ca5a4c184c42414c0b1ebcc1b35ee50938d934ebe0cf3f81d156f5f'
  diagnostic_closure = '76e1c0bc8a176b7cecc1722788f933a65701a53d031bcdbd4ca4358d6ee05e8d'
  diagnostic_failure_seal = 'e0c39ae99b2afb19147b5e03bf959c09028effa3a57c7694f4e325fbfdc35fac'
  diagnostic_run_log = '1226a5b2d03b792f275f98f96334f21ac9cd97e8c309473749299087b2229ada'
  diagnostic_model_log = 'fa50fb132a869ce2c81b05e716484f99d1abc5829d0986941c346a0e642e7f3c'
  diagnostic_v011_input = '567c66db4faa12ab6e82ea72613f6b2d293ab608ebaed6a79f7daf2996e25f9b'
  diagnostic_v011_contract = '847a503ce0543dd77db6a1f6fe64b1567f2524b467be267800b72803dd6d517a'
  diagnostic_v011_runner = 'a2da05975e182aa1c89d89656d9686485a38cfd86b00563048c9c8dbe810fdc8'
  diagnostic_v011_validator = '365f7b2347f8905a465557bd777ce3c4a00224b8990950abb75ec5c45265d809'
  diagnostic_v011_closure = '2897a7ed4825f3e3fd10cd8ff33d7ad21ba0621b40dcd0c0b752fe5df9ae9bd7'
  diagnostic_v011_report = 'f4654be8dd23dd960e476ec54ab7168922b29d97e58559b746e50a82a3e8cf29'
  diagnostic_v011_author = '9943bcb2518b8ef9b840f43ded2b0b5358f554d7a59a19555062946c9d7537f3'
  diagnostic_v011_review = 'ffe320f2afea39a9ab653771331bf6541accb5706b93f150b9554b2b834ad600'
  a03_input = 'd7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4'
  a03_signoff = '6c8d3998f20e216d0403b807866fcbe306f68ebc6f376693334435e808747b2b'
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
if ($sealed.run_id -ne 'a03-var01-one-of-two-v010-ssh-20261006-01' -or $sealed.error -or @($sealed.raw.PSObject.Properties).Count -ne 12) { throw 'accepted A03.var01 parent closure identity/count differs' }
foreach ($artifact in $sealed.raw.PSObject.Properties) {
  $path = Join-Path $parentRun $artifact.Name
  if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne $artifact.Value.bytes -or (Get-Sha $path) -ne $artifact.Value.sha256) { throw "accepted A03.var01 raw seal differs: $($artifact.Name)" }
}
$oldClosure = Get-Content -LiteralPath $sourcePaths.diagnostic_closure -Raw | ConvertFrom-Json
$oldFailure = Get-Content -LiteralPath $sourcePaths.diagnostic_failure_seal -Raw | ConvertFrom-Json
if ($oldClosure.run_id -ne 'a03-var01-zero-v010-ssh-20261006-01' -or $oldClosure.error -ne 'converter diagnostics differ' -or @($oldClosure.raw.PSObject.Properties).Count -ne 10) { throw 'excluded v0.1.0 closure identity/count differs' }
if ($oldFailure.run_id -ne $oldClosure.run_id -or $oldFailure.error -ne $oldClosure.error -or @($oldFailure.files.PSObject.Properties).Count -ne 12) { throw 'excluded v0.1.0 failure seal identity/count differs' }
foreach ($artifact in $oldClosure.raw.PSObject.Properties) {
  $path = Join-Path $diagnosticRun $artifact.Name
  if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne $artifact.Value.bytes -or (Get-Sha $path) -ne $artifact.Value.sha256) { throw "excluded v0.1.0 closure raw seal differs: $($artifact.Name)" }
}
foreach ($artifact in $oldFailure.files.PSObject.Properties) {
  $path = Join-Path $diagnosticRun $artifact.Name
  if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne $artifact.Value.bytes -or (Get-Sha $path) -ne $artifact.Value.sha256) { throw "excluded v0.1.0 failure raw seal differs: $($artifact.Name)" }
}
$oldV011Closure = Get-Content -LiteralPath $sourcePaths.diagnostic_v011_closure -Raw | ConvertFrom-Json
$oldV011Author = Get-Content -LiteralPath $sourcePaths.diagnostic_v011_author -Raw | ConvertFrom-Json
if ($oldV011Closure.run_id -ne 'a03-var01-zero-v011-ssh-20261006-01' -or $oldV011Closure.error -or @($oldV011Closure.raw.PSObject.Properties).Count -ne 12 -or (ConvertTo-Json $oldV011Closure.source_hashes_before -Compress) -ne (ConvertTo-Json $oldV011Closure.source_hashes_after -Compress)) { throw 'excluded v0.1.1 closure identity/count differs' }
if ($oldV011Author.run_id -ne $oldV011Closure.run_id -or $oldV011Author.decision -ne 'NO_GO' -or $oldV011Author.checks -ne 4445 -or @($oldV011Author.failures).Count -ne 72 -or @($oldV011Author.failures | Where-Object { $_ -match 'System\[\d+\]\.FTMO zero' }).Count -ne 72) { throw 'excluded v0.1.1 author NO_GO identity differs' }
foreach ($artifact in $oldV011Closure.raw.PSObject.Properties) {
  $path = Join-Path $diagnosticV011Run $artifact.Name
  if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne $artifact.Value.bytes -or (Get-Sha $path) -ne $artifact.Value.sha256) { throw "excluded v0.1.1 raw seal differs: $($artifact.Name)" }
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
    [ordered]@{schema='simlox-a03-var01-zero-v012-preflight/v1';run_id=$RunId;run_absent=$true;
      ssh_session=0;ssh_ancestors=$ancestors;queue_free=$true;
      gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
      accepted_a03_var01_parent_raw_seals=12;excluded_v010_closure_raw_seals=10;excluded_v010_failure_file_seals=12;excluded_v011_raw_seals=12;source_hashes=$before;native_process_started=$false} | ConvertTo-Json -Depth 7
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
        if ($log -notmatch 'Input conversion completed\. Errors: 0, Warnings: 3, Notes: 1' -or @([regex]::Matches($log,'\(warning #108\)')).Count -ne 1 -or @([regex]::Matches($log,'\(warning #126\)')).Count -ne 1 -or @([regex]::Matches($log,'\(warning #486\)')).Count -ne 1 -or @([regex]::Matches($log,'\(warning #\d+\)')).Count -ne 3 -or @([regex]::Matches($log,'\(notice #184\)')).Count -ne 1 -or @([regex]::Matches($log,'\(notice #\d+\)')).Count -ne 1 -or $log -notmatch 'rec 1: \(notice #184\) Number of systems deployed \(QTYPS\) is zero: TEACH-AIR-01/TEACH-UNIT' -or $log -match '\(error #\d+\)') { throw 'converter diagnostics differ' }
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
  [ordered]@{schema='simlox-a03-var01-zero-v012-native-candidate/ssh-cli-v1';case_id='A03';variant_id='A03.var01';run_id=$RunId;
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
  [ordered]@{schema='simlox-a03-var01-zero-v012-native-closure/v1';run_id=$RunId;
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
      [ordered]@{schema='simlox-a03-var01-zero-v012-failure-seal/v1';run_id=$RunId;error=$failureMessage;
        files=$preserved;publication_state='excluded'} | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath (Join-Path $run 'failure-seal.json') -Encoding UTF8
    } catch { Write-Warning "failure seal write failed: $($_.Exception.Message)" }
  }
  throw $failureMessage
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

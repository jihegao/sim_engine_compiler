param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$nativeInputPath = Join-Path $case 'native-input.json'
$contract = Join-Path $case 'contract.json'
$builderPath = Join-Path $case 'build.py'
$checkerPath = Join-Path $case 'check_roundtrip.py'
$diffCheckerPath = Join-Path $case 'check_parent_diff.py'
$validatorPath = Join-Path $case 'validate_native_cli.py'
$pythonPath = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$parent = Join-Path (Split-Path $case -Parent) 'D04-flight-hour-pm-v1.0.0\native-input.json'
$parentSignoff = Join-Path (Split-Path $case -Parent) 'D04-flight-hour-pm-v1.0.0\cli-scope-signoff-2026-09-30.md'
$parentClosure = Join-Path (Split-Path $case -Parent) 'D04-flight-hour-pm-v1.0.0\runs\d04-flight-v100-ssh-20260930-01\closure.json'
$d03Signoff = Join-Path (Split-Path $case -Parent) 'D03-calendar-pm-v1.0.0\cli-scope-signoff-2026-09-30.md'
$contractReview = Join-Path $case 'review\independent-contract-go-2026-10-06.md'
$negativeControl = Join-Path $case 'review\negative-control-accepted-parent.json'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run = Join-Path (Join-Path $case 'runs') $RunId
if ($RunId -ne 'd04-var01-op4-v010-ssh-20261006-01') { throw 'unreviewed run identity' }
$inputSha = 'cb8d6045df3b395583e3df2290b61376afa4fa9e8bc82a1c6f53fcfb44e2bddd'
$parentSha = 'd0b0ee5b74f3afe5f05b418771774adcf8ef987b0f553f1bfd535874955c790a'
$exeSha = 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
Write-Output 'D04.var01 OP4 threshold native preflight: session'
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if (Test-Path -LiteralPath $run) { throw 'immutable native run already exists' }
$ancestors = @()
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'cannot verify sshd ancestor' }
Write-Output 'D04.var01 OP4 threshold native preflight: source fingerprints'
foreach ($item in @(@($nativeInputPath,$inputSha),@($parent,$parentSha),@($parentSignoff,'44d668fa724b1cf63370c88a560e42d3f4e324071eee720a036d2905185fe831'),@($parentClosure,'3cae72c375ef7a7c8dc63d785a33e97e9bd6103655fc28971abf5a0ccb24df45'),@($d03Signoff,'8c609dc19b1a4b7f027da9538096c5171244609b80cab9026e1ad360cd9006d1'),@($contractReview,'d7b0cd954ed860f5ef31b2283b450b63945648143ef3df87cdf35d46a90dfec8'),@($negativeControl,'51377c0febb5f012d39af5097a7d8eb543e520fe92dd75de024cf84b1a9496dc'),@($manual,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3'),@($exe,$exeSha))) {
  if (-not (Test-Path -LiteralPath $item[0]) -or (Get-FileHash -LiteralPath $item[0] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item[1]) { throw "fingerprint differs: $($item[0])" }
}
$parentRun = Split-Path $parentClosure -Parent
$acceptedClosure = Get-Content -LiteralPath $parentClosure -Raw | ConvertFrom-Json
if ($acceptedClosure.schema -ne 'simlox-d04-flight-v100-native-closure/v1' -or $acceptedClosure.run_id -ne 'd04-flight-v100-ssh-20260930-01' -or $acceptedClosure.error -or @($acceptedClosure.raw.PSObject.Properties).Count -ne 12) { throw 'accepted D04 closure shape/status differs' }
foreach ($seal in $acceptedClosure.raw.PSObject.Properties) {
  $rawPath = Join-Path $parentRun $seal.Name
  if (-not (Test-Path -LiteralPath $rawPath) -or (Get-Item -LiteralPath $rawPath).Length -ne $seal.Value.bytes -or (Get-FileHash -LiteralPath $rawPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $seal.Value.sha256) { throw "accepted D04 raw seal differs: $($seal.Name)" }
}
foreach ($item in @(@('model.log','072310b8b29b69167d1a77df359144ad0b911748e512936271ef44f5009e084c'),@('report-raw.json','48261211d3346de355306cb1ab258a67765bfc9b037843847c673375239fda68'))) {
  if ((Get-FileHash -LiteralPath (Join-Path $parentRun $item[0]) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item[1]) { throw "accepted D04 event/report pin differs: $($item[0])" }
}
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned native working directory absent' }
if (-not (Test-Path -LiteralPath $contract) -or -not (Test-Path -LiteralPath $builderPath) -or -not (Test-Path -LiteralPath $checkerPath) -or -not (Test-Path -LiteralPath $diffCheckerPath) -or -not (Test-Path -LiteralPath $validatorPath) -or -not (Test-Path -LiteralPath $pythonPath)) { throw 'contract, builder, checkers, validator or Python absent' }
$frozenHashes = [ordered]@{
  $contract = '0ee824f2ccc35319f8cd369d961099ecaf3258641f424bdbd875b69af1ce6450'
  $builderPath = '91029a09710ff6478ed735bf2e5f2b4ac1112bd9b10ffe9ea039bbc82f7ced70'
  $checkerPath = 'cd0088939bae73f769658b33ae3079e6b1e539bbb4f1465a66424ad1db978a6b'
  $diffCheckerPath = 'ef672d74ab0dcd88a5d2b180b6e16aaf61653c3470a2c4191e9d443f881307db'
  $validatorPath = '79d3a9c202e1c8a40cb52c58e0963066bd0ce2ddd75a80ed960fadb61ba1a5f0'
}
foreach ($path in $frozenHashes.Keys) {
  if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $frozenHashes[$path]) { throw "prelaunch frozen source differs: $path" }
}
& $pythonPath $builderPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen D04.var01 OP4 builder check failed' }
& $pythonPath $diffCheckerPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen D04.var01 parent diff check failed' }
Write-Output 'D04.var01 OP4 threshold native preflight: queue'
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide Issue 18 native queue busy' }
  Write-Output 'D04.var01 OP4 threshold native preflight: GUI identity'
  $existing = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -ne 1 -or -not $existing[0].Responding -or ([DateTimeOffset]$existing[0].StartTime.ToUniversalTime()).ToUnixTimeMilliseconds() -ne 1790590196826) { throw 'expected responding GUI PID/session/start identity differs' }
  $guiStart = $existing[0].StartTime.ToUniversalTime().ToString('o')
  $guiSession = $existing[0].SessionId
  $sessions = @(qwinsta 2>&1)
  Write-Output 'D04.var01 OP4 threshold native preflight: GUI session'
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session not active' }
  function Assert-Gui {
    $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
    if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $guiSession -or -not $p[0].Responding -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'GUI process changed or unresponsive' }
  }
  New-Item -ItemType Directory -Path $run -Force | Out-Null
  Copy-Item -LiteralPath $nativeInputPath -Destination (Join-Path $run 'input.json')
  if ((Get-FileHash -LiteralPath (Join-Path $run 'input.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $inputSha) { throw 'copied input fingerprint differs' }
  $source = Join-Path $run 'input.json'
  $sxi = Join-Path $run 'model.sxi'
  $sxo = Join-Path $run 'model.sxo'
  $round = Join-Path $run 'roundtrip-raw.json'
  $report = Join-Path $run 'report-raw.json'
  $commands = @(
    [pscustomobject]@{ name='import'; args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $source,$sxi,(Join-Path $run 'import.log')) },
    [pscustomobject]@{ name='export'; args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,$round,(Join-Path $run 'export.log')) },
    [pscustomobject]@{ name='calc'; args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log')) },
    [pscustomobject]@{ name='jsonreport'; args=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,$report,(Join-Path $run 'report-export.log')) }
  )
  $sourceHashesBefore = [ordered]@{
    input = $inputSha
    parent = $parentSha
    parent_signoff = (Get-FileHash -LiteralPath $parentSignoff -Algorithm SHA256).Hash.ToLowerInvariant()
    parent_closure = (Get-FileHash -LiteralPath $parentClosure -Algorithm SHA256).Hash.ToLowerInvariant()
    d03_signoff = (Get-FileHash -LiteralPath $d03Signoff -Algorithm SHA256).Hash.ToLowerInvariant()
    contract_review = (Get-FileHash -LiteralPath $contractReview -Algorithm SHA256).Hash.ToLowerInvariant()
    negative_control = (Get-FileHash -LiteralPath $negativeControl -Algorithm SHA256).Hash.ToLowerInvariant()
    manual_pdf = (Get-FileHash -LiteralPath $manual -Algorithm SHA256).Hash.ToLowerInvariant()
    contract = (Get-FileHash -LiteralPath $contract -Algorithm SHA256).Hash.ToLowerInvariant()
    builder = (Get-FileHash -LiteralPath $builderPath -Algorithm SHA256).Hash.ToLowerInvariant()
    checker = (Get-FileHash -LiteralPath $checkerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    diff_checker = (Get-FileHash -LiteralPath $diffCheckerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    validator = (Get-FileHash -LiteralPath $validatorPath -Algorithm SHA256).Hash.ToLowerInvariant()
    python = (Get-FileHash -LiteralPath $pythonPath -Algorithm SHA256).Hash.ToLowerInvariant()
    runner_script = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    simlox_exe = $exeSha
  }
  $invocation = [ordered]@{
    schema = 'simlox-d04-var01-v010-native-candidate/ssh-cli-v1'
    case_id = 'D04'; variant_id = 'D04.var01'; case_version = '0.1.0-candidate'; run_id = $RunId
    created_utc = (Get-Date).ToUniversalTime().ToString('o')
    original_run_dir = $run; host_name = $env:COMPUTERNAME
    input_sha256 = $inputSha; parent_sha256 = $parentSha
    contract_sha256 = $sourceHashesBefore.contract
    builder_sha256 = $sourceHashesBefore.builder
    checker_sha256 = $sourceHashesBefore.checker
    diff_checker_sha256 = $sourceHashesBefore.diff_checker
    validator_sha256 = $sourceHashesBefore.validator
    python_sha256 = $sourceHashesBefore.python
    runner_script_sha256 = $sourceHashesBefore.runner_script
    simlox_exe_sha256 = $exeSha; working_directory = $workingDirectory
    execution_mode = 'ssh_cli_v1'; session_id = (Get-Process -Id $PID).SessionId
    ssh_connection_present = [bool]$env:SSH_CONNECTION
    ssh_ancestor_names = $ancestors
    gui = [ordered]@{ pid=13340; session_id=$guiSession; start_utc=$guiStart }
    queue_mutex = 'Global\SimloxIssue18NativeQueue'
    planned_commands = @($commands | ForEach-Object { [ordered]@{ name=$_.name; arguments=$_.args } })
    planned_check = [ordered]@{ executable=$pythonPath; arguments=@($checkerPath,$run); output=(Join-Path $run 'roundtrip-validation.json') }
    source_hashes_before = $sourceHashesBefore
    scope = 'four_step_native_candidate'; publication_state = 'not_published'
  }
  $invocation | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps = @()
  $errorText = $null
  foreach ($command in $commands) {
    $step = [ordered]@{ name=$command.name; arguments=$command.args; started_utc=(Get-Date).ToUniversalTime().ToString('o'); completed_utc=$null; exit_code=$null; gui_preserved=$false; status='started'; error=$null }
    $steps += $step
    ConvertTo-Json -InputObject $steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
    try {
      Assert-Gui
      $process = Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru
      if (-not $process.WaitForExit(300000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        $process.WaitForExit(10000) | Out-Null
        throw "$($command.name) timed out after 300 seconds; only launched child PID $($process.Id) stopped"
      }
      $step.exit_code = $process.ExitCode
      Assert-Gui
      $step.gui_preserved = $true
      if ($process.ExitCode -ne 0) { throw "$($command.name) exit=$($process.ExitCode)" }
      $required = switch ($command.name) {
        'import' { @('model.sxi','import.log') }
        'export' { @('roundtrip-raw.json','export.log') }
        'calc' { @('model.sxo','run.log','model.log') }
        'jsonreport' { @('report-raw.json','report-export.log') }
      }
      foreach ($name in $required) {
        $output = Join-Path $run $name
        if (-not (Test-Path -LiteralPath $output) -or (Get-Item -LiteralPath $output).Length -le 4) { throw "$($command.name) output $name absent/empty" }
      }
      if ($command.name -eq 'calc') {
        $calcText = Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw
        if ($calcText -notmatch 'Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0' -or @([regex]::Matches($calcText, '\(warning #108\)')).Count -ne 1 -or @([regex]::Matches($calcText, '\(warning #126\)')).Count -ne 1 -or @([regex]::Matches($calcText, '\(warning #\d+\)')).Count -ne 2 -or $calcText -notmatch 'This system contains no items: TEACH-AIR-01' -or $calcText -match '\(error #\d+\)') { throw 'conversion diagnostics differ from zero errors, warning 108 plus item-free system 126, zero notes' }
      }
      $step.status = 'completed'
    } catch {
      $errorText = $_.Exception.Message
      $step.status = 'failed'
      $step.error = $errorText
      break
    } finally {
      $step.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
      ConvertTo-Json -InputObject $steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
    }
    if (-not $errorText -and $command.name -eq 'export') {
    $step = [ordered]@{ name='check_import_export'; arguments=@($checkerPath,$run); started_utc=(Get-Date).ToUniversalTime().ToString('o'); completed_utc=$null; exit_code=$null; gui_preserved=$false; status='started'; error=$null }
    $steps += $step
    ConvertTo-Json -InputObject $steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
    try {
      Assert-Gui
      & $pythonPath $checkerPath $run | Set-Content -LiteralPath (Join-Path $run 'roundtrip-validation.json') -Encoding UTF8
      $step.exit_code = $LASTEXITCODE
      Assert-Gui
      $step.gui_preserved = $true
      if ($step.exit_code -ne 0) { throw "roundtrip checker exit=$($step.exit_code)" }
      $step.status = 'completed'
    } catch {
      $errorText = $_.Exception.Message
      $step.status = 'failed'
      $step.error = $errorText
    } finally {
      $step.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
      ConvertTo-Json -InputObject $steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
    }
    }
    if ($errorText) { break }
  }
  $sourceHashesAfter = [ordered]@{
    input = (Get-FileHash -LiteralPath $nativeInputPath -Algorithm SHA256).Hash.ToLowerInvariant()
    parent = (Get-FileHash -LiteralPath $parent -Algorithm SHA256).Hash.ToLowerInvariant()
    parent_signoff = (Get-FileHash -LiteralPath $parentSignoff -Algorithm SHA256).Hash.ToLowerInvariant()
    parent_closure = (Get-FileHash -LiteralPath $parentClosure -Algorithm SHA256).Hash.ToLowerInvariant()
    d03_signoff = (Get-FileHash -LiteralPath $d03Signoff -Algorithm SHA256).Hash.ToLowerInvariant()
    contract_review = (Get-FileHash -LiteralPath $contractReview -Algorithm SHA256).Hash.ToLowerInvariant()
    negative_control = (Get-FileHash -LiteralPath $negativeControl -Algorithm SHA256).Hash.ToLowerInvariant()
    manual_pdf = (Get-FileHash -LiteralPath $manual -Algorithm SHA256).Hash.ToLowerInvariant()
    contract = (Get-FileHash -LiteralPath $contract -Algorithm SHA256).Hash.ToLowerInvariant()
    builder = (Get-FileHash -LiteralPath $builderPath -Algorithm SHA256).Hash.ToLowerInvariant()
    checker = (Get-FileHash -LiteralPath $checkerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    diff_checker = (Get-FileHash -LiteralPath $diffCheckerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    validator = (Get-FileHash -LiteralPath $validatorPath -Algorithm SHA256).Hash.ToLowerInvariant()
    python = (Get-FileHash -LiteralPath $pythonPath -Algorithm SHA256).Hash.ToLowerInvariant()
    runner_script = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    simlox_exe = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
  }
  foreach ($key in $sourceHashesBefore.Keys) {
    if ($sourceHashesBefore[$key] -ne $sourceHashesAfter[$key]) { $errorText = "source fingerprint changed during native run: $key" }
  }
  $raw = @{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File) {
    if ($file.Name -eq 'invocation.json') { continue }
    $raw[$file.Name] = [ordered]@{ bytes=$file.Length; sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
  }
  [ordered]@{ schema='simlox-d04-var01-v010-native-closure/v1'; run_id=$RunId; invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant(); source_hashes_before=$sourceHashesBefore; source_hashes_after=$sourceHashesAfter; raw=$raw; error=$errorText; scope='four_step_native_candidate'; publication_state='not_published' } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{ run_id=$RunId; run_dir=$run; native_steps='completed'; scope='four_step_native_candidate' } | ConvertTo-Json)
} catch {
  $failureMessage = $_.Exception.Message
  if (Test-Path -LiteralPath $run) {
    try {
      $preserved = @{}
      foreach ($file in Get-ChildItem -LiteralPath $run -File) {
        if ($file.Name -eq 'failure-seal.json') { continue }
        $preserved[$file.Name] = [ordered]@{ bytes=$file.Length; sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
      }
      [ordered]@{ schema='simlox-d04-var01-v010-failure-seal/v1'; run_id=$RunId; error=$failureMessage; files=$preserved; publication_state='excluded' } |
        ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'failure-seal.json') -Encoding UTF8
    } catch { Write-Warning "failure seal could not be written: $($_.Exception.Message)" }
  }
  throw $failureMessage
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

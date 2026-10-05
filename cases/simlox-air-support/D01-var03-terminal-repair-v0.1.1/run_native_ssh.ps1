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
$parent = Join-Path (Split-Path $case -Parent) 'D01-system-direct-repair-v1.0.0\native-input.json'
$parentSignoff = Join-Path (Split-Path $case -Parent) 'D01-system-direct-repair-v1.0.0\cli-scope-signoff-2026-09-29.md'
$parentClosure = Join-Path (Split-Path $case -Parent) 'D01-system-direct-repair-v1.0.0\runs\d01-v100-ssh-20260929-01\closure.json'
$a02Signoff = Join-Path (Split-Path $case -Parent) 'A02-single-aircraft-repeated-missions\cli-scope-signoff-2026-09-29.md'
$j05Signoff = Join-Path (Split-Path $case -Parent) 'J05-collection-window-v1.0.1\cli-scope-signoff-2026-10-01.md'
$d05Signoff = Join-Path (Split-Path $case -Parent) 'D05-var04-horizon-in-repair-v1.0.0\cli-scope-signoff-2026-09-30.md'
$precursor = Join-Path (Split-Path $case -Parent) 'D01-var03-terminal-repair-v0.1.0'
$precursorRun = Join-Path $precursor 'runs\d01-var03-terminal-v010-ssh-20261006-01'
$precursorClosure = Join-Path $precursorRun 'closure.json'
$precursorFailure = Join-Path $precursorRun 'failure-seal.json'
$precursorReview = Join-Path $precursor 'review\independent-postfailure-2026-10-06.md'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run = Join-Path (Join-Path $case 'runs') $RunId
if ($RunId -ne 'd01-var03-terminal-v011-ssh-20261006-01') { throw 'unreviewed run identity' }
$inputSha = '0b9f8d05d56025e4e3d6658c41c61bdfb65dd900d7f4a60885b8cfd00531cfca'
$parentSha = 'd418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450'
$exeSha = 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
Write-Output 'D01.var03 native preflight: session'
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
Write-Output 'D01.var03 native preflight: source fingerprints'
foreach ($item in @(@($nativeInputPath,$inputSha),@($parent,$parentSha),@($parentSignoff,'428224849277100ebd7b97f068308e43617884759cb3a82e1792ddebeae772b3'),@($parentClosure,'c3769da04ae3e8e754ff172cb0bed9317a0ec7ec5352913086341cc0ad489c05'),@($a02Signoff,'608eef828a65ef7a8c738a3ec227b890421c29248ee8addd9e992a4c7e7e919e'),@($j05Signoff,'8c30b1b1a563c2350431fe7978eea12ae8c33bd112584dc3b53006d509ba9e95'),@($d05Signoff,'6a6f2c82c027e84fee22b8895f2bb53d4af2d65749846a76a074a0abab2ae22f'),@($precursorClosure,'dadd724454ec461a83e75946b54cb4a50e7cee57b777ad00cf842949a4dce5f2'),@($precursorFailure,'40fde15b06ae281cd0c6042ee02ad1ae510e0e6554aea156aac9ffcbba9e51a1'),@($precursorReview,'18b829c6d61e26e3aeb97e9ceab4a56ecc686ddb89a53ae9d82158b246d9d6d7'),@($exe,$exeSha))) {
  if (-not (Test-Path -LiteralPath $item[0]) -or (Get-FileHash -LiteralPath $item[0] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item[1]) { throw "fingerprint differs: $($item[0])" }
}
$excludedClosure = Get-Content -LiteralPath $precursorClosure -Raw | ConvertFrom-Json
if ($excludedClosure.schema -ne 'simlox-d01-var03-v010-native-closure/v1' -or $excludedClosure.run_id -ne 'd01-var03-terminal-v010-ssh-20261006-01' -or $excludedClosure.error -ne 'calc output model.sxo absent/empty' -or @($excludedClosure.raw.PSObject.Properties).Count -ne 9) { throw 'excluded precursor closure differs' }
foreach ($seal in $excludedClosure.raw.PSObject.Properties) {
  $rawPath = Join-Path $precursorRun $seal.Name
  if (-not (Test-Path -LiteralPath $rawPath) -or (Get-Item -LiteralPath $rawPath).Length -ne $seal.Value.bytes -or (Get-FileHash -LiteralPath $rawPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $seal.Value.sha256) { throw "excluded precursor raw seal differs: $($seal.Name)" }
}
$excludedFailure = Get-Content -LiteralPath $precursorFailure -Raw | ConvertFrom-Json
if ($excludedFailure.schema -ne 'simlox-d01-var03-v010-failure-seal/v1' -or @($excludedFailure.files.PSObject.Properties).Count -ne 11) { throw 'excluded precursor failure seal differs' }
foreach ($seal in $excludedFailure.files.PSObject.Properties) {
  $rawPath = Join-Path $precursorRun $seal.Name
  if (-not (Test-Path -LiteralPath $rawPath) -or (Get-Item -LiteralPath $rawPath).Length -ne $seal.Value.bytes -or (Get-FileHash -LiteralPath $rawPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $seal.Value.sha256) { throw "excluded precursor failure file differs: $($seal.Name)" }
}
$parentRun = Split-Path $parentClosure -Parent
$acceptedClosure = Get-Content -LiteralPath $parentClosure -Raw | ConvertFrom-Json
if ($acceptedClosure.schema -ne 'simlox-d01-v100-native-closure/v1' -or $acceptedClosure.run_id -ne 'd01-v100-ssh-20260929-01' -or $acceptedClosure.error -or @($acceptedClosure.raw.PSObject.Properties).Count -ne 12) { throw 'accepted D01 closure shape/status differs' }
foreach ($seal in $acceptedClosure.raw.PSObject.Properties) {
  $rawPath = Join-Path $parentRun $seal.Name
  if (-not (Test-Path -LiteralPath $rawPath) -or (Get-Item -LiteralPath $rawPath).Length -ne $seal.Value.bytes -or (Get-FileHash -LiteralPath $rawPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $seal.Value.sha256) { throw "accepted D01 raw seal differs: $($seal.Name)" }
}
foreach ($item in @(@('model.log','71c46a192990c81bf27ed6fd1b41ea15b5ada25834131a7700d4d1b779e83161'),@('report-raw.json','cb21d4b6f7c3c35b8d42412e60bb6ca85d178b4ef6e9d61d71ca294ba94fc83a'))) {
  $path = Join-Path $parentRun $item[0]
  if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item[1]) { throw "accepted D01 parent event/report pin differs: $path" }
}
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned native working directory absent' }
if (-not (Test-Path -LiteralPath $contract) -or -not (Test-Path -LiteralPath $builderPath) -or -not (Test-Path -LiteralPath $checkerPath) -or -not (Test-Path -LiteralPath $diffCheckerPath) -or -not (Test-Path -LiteralPath $validatorPath) -or -not (Test-Path -LiteralPath $pythonPath)) { throw 'contract, builder, checkers, validator or Python absent' }
$frozenHashes = [ordered]@{
  $contract = 'c5fe170e7a7370d51de4f2f5b08204d982cc6c44272f5eed97f9354e852ab6b7'
  $builderPath = '271cc2bb4d5db523f2dad522a44954014ef7f07832f853df59c4a2f416a811be'
  $checkerPath = '9096b2f2ba680129a1644a9c3fff3fc9c405ff7479794a47ed4310333cc4df03'
  $diffCheckerPath = '5e2fab09d85dd4a78c1cc47cfe7923c792d3cc4e71739c6052e7a4f6983180b7'
  $validatorPath = 'd5b78801732979c1412ec22bec138250d36ec0d678197e44acbf0ebe96a8f953'
}
foreach ($path in $frozenHashes.Keys) {
  if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $frozenHashes[$path]) { throw "prelaunch frozen source differs: $path" }
}
& $pythonPath $builderPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen D01.var03 builder check failed' }
& $pythonPath $diffCheckerPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen D01.var03 parent diff check failed' }
Write-Output 'D01.var03 native preflight: queue'
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide Issue 18 native queue busy' }
  Write-Output 'D01.var03 native preflight: GUI identity'
  $existing = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -ne 1 -or -not $existing[0].Responding -or ([DateTimeOffset]$existing[0].StartTime.ToUniversalTime()).ToUnixTimeMilliseconds() -ne 1790590196826) { throw 'expected responding GUI PID/session/start identity differs' }
  $guiStart = $existing[0].StartTime.ToUniversalTime().ToString('o')
  $guiSession = $existing[0].SessionId
  $sessions = @(qwinsta 2>&1)
  Write-Output 'D01.var03 native preflight: GUI session'
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
    a02_signoff = (Get-FileHash -LiteralPath $a02Signoff -Algorithm SHA256).Hash.ToLowerInvariant()
    j05_signoff = (Get-FileHash -LiteralPath $j05Signoff -Algorithm SHA256).Hash.ToLowerInvariant()
    d05_signoff = (Get-FileHash -LiteralPath $d05Signoff -Algorithm SHA256).Hash.ToLowerInvariant()
    precursor_closure = (Get-FileHash -LiteralPath $precursorClosure -Algorithm SHA256).Hash.ToLowerInvariant()
    precursor_failure_seal = (Get-FileHash -LiteralPath $precursorFailure -Algorithm SHA256).Hash.ToLowerInvariant()
    precursor_independent_review = (Get-FileHash -LiteralPath $precursorReview -Algorithm SHA256).Hash.ToLowerInvariant()
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
    schema = 'simlox-d01-var03-v011-native-candidate/ssh-cli-v1'
    case_id = 'D01'; variant_id = 'D01.var03'; case_version = '0.1.1-candidate'; run_id = $RunId
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
    a02_signoff = (Get-FileHash -LiteralPath $a02Signoff -Algorithm SHA256).Hash.ToLowerInvariant()
    j05_signoff = (Get-FileHash -LiteralPath $j05Signoff -Algorithm SHA256).Hash.ToLowerInvariant()
    d05_signoff = (Get-FileHash -LiteralPath $d05Signoff -Algorithm SHA256).Hash.ToLowerInvariant()
    precursor_closure = (Get-FileHash -LiteralPath $precursorClosure -Algorithm SHA256).Hash.ToLowerInvariant()
    precursor_failure_seal = (Get-FileHash -LiteralPath $precursorFailure -Algorithm SHA256).Hash.ToLowerInvariant()
    precursor_independent_review = (Get-FileHash -LiteralPath $precursorReview -Algorithm SHA256).Hash.ToLowerInvariant()
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
  [ordered]@{ schema='simlox-d01-var03-v011-native-closure/v1'; run_id=$RunId; invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant(); source_hashes_before=$sourceHashesBefore; source_hashes_after=$sourceHashesAfter; raw=$raw; error=$errorText; scope='four_step_native_candidate'; publication_state='not_published' } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
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
      [ordered]@{ schema='simlox-d01-var03-v011-failure-seal/v1'; run_id=$RunId; error=$failureMessage; files=$preserved; publication_state='excluded' } |
        ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'failure-seal.json') -Encoding UTF8
    } catch { Write-Warning "failure seal could not be written: $($_.Exception.Message)" }
  }
  throw $failureMessage
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

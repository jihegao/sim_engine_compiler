param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
  [Parameter(Mandatory=$true)][ValidateSet('minbs1','minbs2')][string]$Arm
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$nativeInputPath = Join-Path $case "native-input-$Arm.json"
$contract = Join-Path $case 'contract.json'
$exactDiffPath = Join-Path $case 'exact-diff.json'
$diffBuilderPath = Join-Path $case 'describe_diff.py'
$builderPath = Join-Path $case 'build.py'
$checkerPath = Join-Path $case 'check_roundtrip.py'
$pythonPath = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$parentMinbs1 = Join-Path (Split-Path $case -Parent) 'E10-var06-minbs-same-item-v1.0.0\native-input-minbs1.json'
$parentMinbs2 = Join-Path (Split-Path $case -Parent) 'E10-var06-minbs-same-item-v1.0.0\native-input-minbs2.json'
$parentClosure1 = Join-Path (Split-Path $case -Parent) 'E10-var06-minbs-same-item-v1.0.0\runs\e10-var06-minbs1-v100-ssh-20261003-01\closure.json'
$parentClosure2 = Join-Path (Split-Path $case -Parent) 'E10-var06-minbs-same-item-v1.0.0\runs\e10-var06-minbs2-v100-ssh-20261003-01\closure.json'
$parentIndex = Join-Path (Split-Path $case -Parent) 'E10-var06-minbs-same-item-v1.0.0\evidence-index.json'
$diagnosticClosure1 = Join-Path (Split-Path $case -Parent) 'E10-var06-minbs-mixed-item-v1.0.0\runs\e10-var06-mixed-minbs1-v100-ssh-20261003-01\closure.json'
$diagnosticClosure2 = Join-Path (Split-Path $case -Parent) 'E10-var06-minbs-mixed-item-v1.0.0\runs\e10-var06-mixed-minbs2-v100-ssh-20261003-01\closure.json'
$diagnosticClosure3 = Join-Path (Split-Path $case -Parent) 'E10-var06-minbs-mixed-item-v1.0.1\runs\e10-var06-mixed-minbs1-v101-ssh-20261003-01\closure.json'
$diagnosticClosure4 = Join-Path (Split-Path $case -Parent) 'E10-var06-minbs-mixed-item-v1.0.1\runs\e10-var06-mixed-minbs2-v101-ssh-20261003-01\closure.json'
$diagnosticClosure5 = Join-Path (Split-Path $case -Parent) 'E10-var06-minbs-mixed-item-v1.0.2\runs\e10-var06-mixed-minbs1-v102-ssh-20261003-01\closure.json'
$diagnosticClosure6 = Join-Path (Split-Path $case -Parent) 'E10-var06-minbs-mixed-item-v1.0.2\runs\e10-var06-mixed-minbs2-v102-ssh-20261003-01\closure.json'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary = 'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run = Join-Path (Join-Path $case 'runs') $RunId
$inputSha = @{ 'minbs1'='ab55c0fb089a87af3f3d8162dec2f19cb819ae4c0b153987d4a311e57de7f296'; 'minbs2'='3c0d239e9ae284fcd00048629c77ad2b6245c7f463f9db0109d15d56ba640504' }[$Arm]
$parentSha1 = '86a52bff52982382d7695ae0a24285b124754d1373fbcd7f3f9340557b31c1ea'
$parentSha2 = 'afff86d9f131ffdb4478fa8a519be3da987579689313a317e7373738dba43a24'
$parentClosureSha1 = '76b5e93a5c827c988106ef5f3020f110b2686ec6372e3acc2e7c1cfcc6c81de1'
$parentClosureSha2 = '7f46c364aa4556b2bce8fe008df8fe7b38aeecd7736d72fa31ff8a6bdbcc7c00'
$parentIndexSha = '6259763364d4f16567c8c289c77a6ed9f8408497c0d69cd7572155e6761dad30'
$diagnosticClosureSha1 = '942a8aea353671f7a00c58571ef82a9ebdd74529bc72f00cbbf669513fa99354'
$diagnosticClosureSha2 = '07d857dd0d1e63bd1b1cd99f76f54f8cc8cf6b0dbe72fa8e491a5ed2aab0efc3'
$diagnosticClosureSha3 = 'fe15296d47afd2f3da8fda2ad0de12b82127717c07e8f0ade9e90d6d5c1e7ff9'
$diagnosticClosureSha4 = '48f73dbeabfcceff68a0fcc34ceec7fb1845c064d9ae2d09e796b7a265c7d15f'
$diagnosticClosureSha5 = '9d49bebebe8fdf8a133c092d1bf6fc0b6b258d9c346623cbbdd60ca5e3e02eea'
$diagnosticClosureSha6 = '9be44b51c6bccdee0233a252752e625b435bb32223c874c38933921fc4377317'
$exeSha = 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
$manualSha = '39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3'
$dictionarySha = '11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0'
$contractSha = '0efc95b7993707479cce97d0146416c55916c72ef0cd49ccdb9acca739cfa971'
$exactDiffSha = '79aa7723b2a7f005777cd60d7e8cf00f124c912573549e0c468e65c3ac9b2834'
Write-Output 'E10.var06 MINBS native preflight: session'
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
Write-Output 'E10.var06 mixed-IID MINBS native preflight: source fingerprints'
foreach ($item in @(@($nativeInputPath,$inputSha),@($parentMinbs1,$parentSha1),@($parentMinbs2,$parentSha2),@($parentClosure1,$parentClosureSha1),@($parentClosure2,$parentClosureSha2),@($parentIndex,$parentIndexSha),@($diagnosticClosure1,$diagnosticClosureSha1),@($diagnosticClosure2,$diagnosticClosureSha2),@($diagnosticClosure3,$diagnosticClosureSha3),@($diagnosticClosure4,$diagnosticClosureSha4),@($diagnosticClosure5,$diagnosticClosureSha5),@($diagnosticClosure6,$diagnosticClosureSha6),@($exe,$exeSha),@($manual,$manualSha),@($dictionary,$dictionarySha),@($contract,$contractSha),@($exactDiffPath,$exactDiffSha))) {
  if (-not (Test-Path -LiteralPath $item[0]) -or (Get-FileHash -LiteralPath $item[0] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item[1]) { throw "fingerprint differs: $($item[0])" }
}
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned native working directory absent' }
if (-not (Test-Path -LiteralPath $builderPath) -or -not (Test-Path -LiteralPath $diffBuilderPath) -or -not (Test-Path -LiteralPath $checkerPath) -or -not (Test-Path -LiteralPath $pythonPath)) { throw 'builder, diff builder, checker or Python absent' }
$frozenContract = Get-Content -LiteralPath $contract -Raw | ConvertFrom-Json
if ($frozenContract.case_id -ne 'E10' -or $frozenContract.variant_id -ne 'E10.var06' -or $frozenContract.case_version -ne '1.0.3-candidate' -or $frozenContract.native_inputs_sha256.$Arm -ne $inputSha -or $frozenContract.accepted_parent.input_sha256.minbs1 -ne $parentSha1 -or $frozenContract.accepted_parent.input_sha256.minbs2 -ne $parentSha2 -or $frozenContract.accepted_parent.native_closure_sha256.minbs1 -ne $parentClosureSha1 -or $frozenContract.accepted_parent.native_closure_sha256.minbs2 -ne $parentClosureSha2 -or $frozenContract.accepted_parent.evidence_index_sha256 -ne $parentIndexSha -or $frozenContract.prior_diagnostic_no_go.native_closure_sha256.minbs1 -ne $diagnosticClosureSha1 -or $frozenContract.prior_diagnostic_no_go.native_closure_sha256.minbs2 -ne $diagnosticClosureSha2 -or $frozenContract.second_diagnostic_no_go.native_closure_sha256.minbs1 -ne $diagnosticClosureSha3 -or $frozenContract.second_diagnostic_no_go.native_closure_sha256.minbs2 -ne $diagnosticClosureSha4 -or $frozenContract.third_diagnostic_no_go.native_closure_sha256.minbs1 -ne $diagnosticClosureSha5 -or $frozenContract.third_diagnostic_no_go.native_closure_sha256.minbs2 -ne $diagnosticClosureSha6 -or $frozenContract.exact_diff_sha256 -ne $exactDiffSha) { throw 'frozen E10.var06 mixed-IID contract source pins differ' }
& $pythonPath $builderPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen E10 builder check failed' }
& $pythonPath $diffBuilderPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen E10 exact-diff check failed' }
Write-Output 'E10.var06 MINBS native preflight: queue'
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide Issue 18 native queue busy' }
  Write-Output 'E10.var06 MINBS native preflight: GUI identity'
  $existing = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -le 0) { throw 'expected existing GUI PID 13340 only' }
  $guiStart = $existing[0].StartTime.ToUniversalTime().ToString('o')
  $guiSession = $existing[0].SessionId
  $sessions = @(qwinsta 2>&1)
  Write-Output 'E10.var06 MINBS native preflight: GUI session'
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session not active' }
  function Assert-Gui {
    $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
    if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'GUI process changed' }
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
    parent_minbs1 = $parentSha1
    parent_minbs2 = $parentSha2
    parent_closure_minbs1 = $parentClosureSha1
    parent_closure_minbs2 = $parentClosureSha2
    parent_index = $parentIndexSha
    prior_diagnostic_closure_minbs1 = $diagnosticClosureSha1
    prior_diagnostic_closure_minbs2 = $diagnosticClosureSha2
    second_diagnostic_closure_minbs1 = $diagnosticClosureSha3
    second_diagnostic_closure_minbs2 = $diagnosticClosureSha4
    third_diagnostic_closure_minbs1 = $diagnosticClosureSha5
    third_diagnostic_closure_minbs2 = $diagnosticClosureSha6
    contract = (Get-FileHash -LiteralPath $contract -Algorithm SHA256).Hash.ToLowerInvariant()
    exact_diff = (Get-FileHash -LiteralPath $exactDiffPath -Algorithm SHA256).Hash.ToLowerInvariant()
    builder = (Get-FileHash -LiteralPath $builderPath -Algorithm SHA256).Hash.ToLowerInvariant()
    diff_builder = (Get-FileHash -LiteralPath $diffBuilderPath -Algorithm SHA256).Hash.ToLowerInvariant()
    checker = (Get-FileHash -LiteralPath $checkerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    python = (Get-FileHash -LiteralPath $pythonPath -Algorithm SHA256).Hash.ToLowerInvariant()
    runner_script = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    simlox_exe = $exeSha
    manual = $manualSha
    dictionary = $dictionarySha
  }
  $invocation = [ordered]@{
    schema = 'simlox-e10-var06-minbs-mixed-item-v103-native-candidate/ssh-cli-v1'
    case_id = 'E10'; variant_id='E10.var06'; case_version = '1.0.3-candidate'; arm = $Arm; run_id = $RunId
    created_utc = (Get-Date).ToUniversalTime().ToString('o')
    original_run_dir = $run; host_name = $env:COMPUTERNAME
    input_sha256 = $inputSha; parent_sha256 = @{ minbs1=$parentSha1; minbs2=$parentSha2 }
    contract_sha256 = $sourceHashesBefore.contract
    exact_diff_sha256 = $sourceHashesBefore.exact_diff
    builder_sha256 = $sourceHashesBefore.builder
    checker_sha256 = $sourceHashesBefore.checker
    python_sha256 = $sourceHashesBefore.python
    runner_script_sha256 = $sourceHashesBefore.runner_script
    simlox_exe_sha256 = $exeSha; working_directory = $workingDirectory
    execution_mode = 'ssh_cli_v1'; session_id = (Get-Process -Id $PID).SessionId
    ssh_connection_present = [bool]$env:SSH_CONNECTION
    ssh_ancestor_names = $ancestors
    gui = [ordered]@{ pid=13340; session_id=$guiSession; start_utc=$guiStart }
    queue_mutex = 'Global\SimloxIssue18NativeQueue'
    planned_commands = @($commands | ForEach-Object { [ordered]@{ name=$_.name; arguments=$_.args } })
    planned_check = [ordered]@{ executable=$pythonPath; arguments=@($checkerPath,$run,$Arm); output=(Join-Path $run 'roundtrip-validation.json') }
    source_hashes_before = $sourceHashesBefore
    scope = 'five_step_native_candidate'; publication_state = 'not_published'
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
      $process = Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
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
        $conversionLog = Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw
        if ($conversionLog -notmatch 'Input conversion completed\. Errors: 0, Warnings: \d+, Notes: \d+') { throw 'native conversion did not report zero errors' }
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
  }
  if (-not $errorText) {
    $step = [ordered]@{ name='check_import_export'; arguments=@($checkerPath,$run,$Arm); started_utc=(Get-Date).ToUniversalTime().ToString('o'); completed_utc=$null; exit_code=$null; gui_preserved=$false; status='started'; error=$null }
    $steps += $step
    ConvertTo-Json -InputObject $steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
    try {
      Assert-Gui
      & $pythonPath $checkerPath $run $Arm | Set-Content -LiteralPath (Join-Path $run 'roundtrip-validation.json') -Encoding UTF8
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
  $sourceHashesAfter = [ordered]@{
    input = (Get-FileHash -LiteralPath $nativeInputPath -Algorithm SHA256).Hash.ToLowerInvariant()
    parent_minbs1 = (Get-FileHash -LiteralPath $parentMinbs1 -Algorithm SHA256).Hash.ToLowerInvariant()
    parent_minbs2 = (Get-FileHash -LiteralPath $parentMinbs2 -Algorithm SHA256).Hash.ToLowerInvariant()
    parent_closure_minbs1 = (Get-FileHash -LiteralPath $parentClosure1 -Algorithm SHA256).Hash.ToLowerInvariant()
    parent_closure_minbs2 = (Get-FileHash -LiteralPath $parentClosure2 -Algorithm SHA256).Hash.ToLowerInvariant()
    parent_index = (Get-FileHash -LiteralPath $parentIndex -Algorithm SHA256).Hash.ToLowerInvariant()
    prior_diagnostic_closure_minbs1 = (Get-FileHash -LiteralPath $diagnosticClosure1 -Algorithm SHA256).Hash.ToLowerInvariant()
    prior_diagnostic_closure_minbs2 = (Get-FileHash -LiteralPath $diagnosticClosure2 -Algorithm SHA256).Hash.ToLowerInvariant()
    second_diagnostic_closure_minbs1 = (Get-FileHash -LiteralPath $diagnosticClosure3 -Algorithm SHA256).Hash.ToLowerInvariant()
    second_diagnostic_closure_minbs2 = (Get-FileHash -LiteralPath $diagnosticClosure4 -Algorithm SHA256).Hash.ToLowerInvariant()
    third_diagnostic_closure_minbs1 = (Get-FileHash -LiteralPath $diagnosticClosure5 -Algorithm SHA256).Hash.ToLowerInvariant()
    third_diagnostic_closure_minbs2 = (Get-FileHash -LiteralPath $diagnosticClosure6 -Algorithm SHA256).Hash.ToLowerInvariant()
    contract = (Get-FileHash -LiteralPath $contract -Algorithm SHA256).Hash.ToLowerInvariant()
    exact_diff = (Get-FileHash -LiteralPath $exactDiffPath -Algorithm SHA256).Hash.ToLowerInvariant()
    builder = (Get-FileHash -LiteralPath $builderPath -Algorithm SHA256).Hash.ToLowerInvariant()
    diff_builder = (Get-FileHash -LiteralPath $diffBuilderPath -Algorithm SHA256).Hash.ToLowerInvariant()
    checker = (Get-FileHash -LiteralPath $checkerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    python = (Get-FileHash -LiteralPath $pythonPath -Algorithm SHA256).Hash.ToLowerInvariant()
    runner_script = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    simlox_exe = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
    manual = (Get-FileHash -LiteralPath $manual -Algorithm SHA256).Hash.ToLowerInvariant()
    dictionary = (Get-FileHash -LiteralPath $dictionary -Algorithm SHA256).Hash.ToLowerInvariant()
  }
  foreach ($key in $sourceHashesBefore.Keys) {
    if ($sourceHashesBefore[$key] -ne $sourceHashesAfter[$key]) { $errorText = "source fingerprint changed during native run: $key" }
  }
  $raw = @{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File) {
    if ($file.Name -eq 'invocation.json') { continue }
    $raw[$file.Name] = [ordered]@{ bytes=$file.Length; sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
  }
  [ordered]@{ schema='simlox-e10-var06-minbs-mixed-item-v103-native-closure/v1'; arm=$Arm; run_id=$RunId; invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant(); source_hashes_before=$sourceHashesBefore; source_hashes_after=$sourceHashesAfter; raw=$raw; error=$errorText; scope='five_step_native_candidate'; publication_state='not_published' } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{ run_id=$RunId; run_dir=$run; native_steps='completed'; scope='five_step_native_candidate' } | ConvertTo-Json)
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

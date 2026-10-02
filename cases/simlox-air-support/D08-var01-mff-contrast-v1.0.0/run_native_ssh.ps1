param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
  [Parameter(Mandatory=$true)][ValidateSet('default','low')][string]$Arm
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
$parent = Join-Path (Split-Path $case -Parent) 'D05-maintenance-competition-v1.0.0\native-input.json'
$catalogParent = Join-Path (Split-Path $case -Parent) 'D02-var01-traditional-op-hours-v1.0.0\native-input.json'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary = 'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run = Join-Path (Join-Path $case 'runs') $RunId
$inputSha = @{ 'default'='5be5592989ac38349141d22c9b9bd5f9db11029182f66bbb456207bb908ae030'; 'low'='f4e82b497668a016f79fd2e8f54f7c6df59e1b8a5a9a1f0c084eb8cfcb6b2d66' }[$Arm]
$parentSha = '4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad'
$catalogParentSha = '9e6d264330c6f7b41752ed8b0c09a32ac45089cec9ec823ad5e3367ce7f348e2'
$exeSha = 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
$manualSha = '39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3'
$dictionarySha = '11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0'
$contractSha = 'bc9565bd159ef5c9413c7c34a12e5d13f535a6f3b4363663765b4276435a44f2'
$exactDiffSha = '4dad45d1518e1411b26c0b9f9581b77e44e5dd70b1a5e4368e99ea5ee8e65f5b'
Write-Output 'D08.var01 MFF native preflight: session'
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
Write-Output 'D08.var01 MFF native preflight: source fingerprints'
foreach ($item in @(@($nativeInputPath,$inputSha),@($parent,$parentSha),@($catalogParent,$catalogParentSha),@($exe,$exeSha),@($manual,$manualSha),@($dictionary,$dictionarySha),@($contract,$contractSha),@($exactDiffPath,$exactDiffSha))) {
  if (-not (Test-Path -LiteralPath $item[0]) -or (Get-FileHash -LiteralPath $item[0] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item[1]) { throw "fingerprint differs: $($item[0])" }
}
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned native working directory absent' }
if (-not (Test-Path -LiteralPath $builderPath) -or -not (Test-Path -LiteralPath $diffBuilderPath) -or -not (Test-Path -LiteralPath $checkerPath) -or -not (Test-Path -LiteralPath $pythonPath)) { throw 'builder, diff builder, checker or Python absent' }
$frozenContract = Get-Content -LiteralPath $contract -Raw | ConvertFrom-Json
if ($frozenContract.case_id -ne 'D08' -or $frozenContract.variant_id -ne 'D08.var01' -or $frozenContract.arms.$Arm.input_sha256 -ne $inputSha -or $frozenContract.direct_behavioral_donor.input_sha256 -ne $parentSha -or $frozenContract.catalog_parent_prerequisite.input_sha256 -ne $catalogParentSha) { throw 'frozen D08 contract source pins differ' }
& $pythonPath $builderPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen D08 builder check failed' }
& $pythonPath $diffBuilderPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen D08 exact-diff check failed' }
Write-Output 'D08.var01 MFF native preflight: queue'
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide Issue 18 native queue busy' }
  Write-Output 'D08.var01 MFF native preflight: GUI identity'
  $existing = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -le 0) { throw 'expected existing GUI PID 13340 only' }
  $guiStart = $existing[0].StartTime.ToUniversalTime().ToString('o')
  $guiSession = $existing[0].SessionId
  $sessions = @(qwinsta 2>&1)
  Write-Output 'D08.var01 MFF native preflight: GUI session'
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
    parent = $parentSha
    catalog_parent = $catalogParentSha
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
    schema = 'simlox-d08-var01-mff-v100-native-candidate/ssh-cli-v1'
    case_id = 'D08'; variant_id='D08.var01'; case_version = '1.0.0-candidate'; arm = $Arm; run_id = $RunId
    created_utc = (Get-Date).ToUniversalTime().ToString('o')
    original_run_dir = $run; host_name = $env:COMPUTERNAME
    input_sha256 = $inputSha; parent_sha256 = $parentSha; catalog_parent_sha256 = $catalogParentSha
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
        if ($conversionLog -notmatch 'Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0') { throw 'native conversion did not report zero errors and expected two warnings' }
        $warningNumbers = @([regex]::Matches($conversionLog, '\(warning #(\d+)\)') | ForEach-Object { $_.Groups[1].Value } | Sort-Object)
        if (($warningNumbers -join ',') -ne '108,126') { throw 'unexpected native converter warning set' }
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
    parent = (Get-FileHash -LiteralPath $parent -Algorithm SHA256).Hash.ToLowerInvariant()
    catalog_parent = (Get-FileHash -LiteralPath $catalogParent -Algorithm SHA256).Hash.ToLowerInvariant()
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
  [ordered]@{ schema='simlox-d08-var01-mff-v100-native-closure/v1'; arm=$Arm; run_id=$RunId; invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant(); source_hashes_before=$sourceHashesBefore; source_hashes_after=$sourceHashesAfter; raw=$raw; error=$errorText; scope='five_step_native_candidate'; publication_state='not_published' } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{ run_id=$RunId; run_dir=$run; native_steps='completed'; scope='five_step_native_candidate' } | ConvertTo-Json)
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$nativeInputPath = Join-Path $case 'native-input.json'
$contract = Join-Path $case 'contract.json'
$builderPath = Join-Path $case 'build.py'
$checkerPath = Join-Path $case 'check_roundtrip.py'
$pythonPath = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$parent = Join-Path (Split-Path $case -Parent) 'G10-var03-nrlrq-crossing-v1.0.0\native-input.json'
$parentSignoff = Join-Path (Split-Path $case -Parent) 'G10-var03-nrlrq-crossing-v1.0.0\cli-scope-signoff-2026-10-03.md'
$parentClosure = Join-Path (Split-Path $case -Parent) 'G10-var03-nrlrq-crossing-v1.0.0\runs\g10-var03-nrlrq-crossing-v100-ssh-20261003-01\closure.json'
$donor = Join-Path (Split-Path $case -Parent) 'G05-unavailable-standby-v1.0.3\unavailable-input.json'
$donorSignoff = Join-Path (Split-Path $case -Parent) 'G05-unavailable-standby-v1.0.3\cli-scope-signoff-2026-10-02.md'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary = 'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run = Join-Path (Join-Path $case 'runs') $RunId
$inputSha = '501924dfde54c81528ccb06cee5320111b2338db59f852f0e26be59d2f77ff35'
$parentSha = 'df9966f1bee58561b1bd54d05ced353abefc37efcd7559c47af5c63683aaa718'
$contractSha = '3b8796ffb389faedc197bd0cbe1b6e599ed8de7956caf4ad9d69363ca37b5a66'
$parentSignoffSha = '918c9441541fda56b3ffd3750a7d77e2bb59a1afe934efce92643eac409209f8'
$parentClosureSha = '84e33e3b751a30274cb0659ea4ccd42d203d10bafd7461f8f19ca94f0478192c'
$donorSha = 'b0d79caeb71dbf991291b9122dff3139bc52c27e2c014b5bf624632539101f0d'
$donorSignoffSha = 'dff875a04c0f33f49cb5a4174339c09a19a11f0508e7f9d8209881495704435d'
$manualSha = '39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3'
$dictionarySha = '11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0'
$exeSha = 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
Write-Output 'G10.var06 native preflight: session'
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
Write-Output 'G10.var06 native preflight: source fingerprints'
foreach ($item in @(@($nativeInputPath,$inputSha),@($parent,$parentSha),@($contract,$contractSha),@($parentSignoff,$parentSignoffSha),@($parentClosure,$parentClosureSha),@($donor,$donorSha),@($donorSignoff,$donorSignoffSha),@($manual,$manualSha),@($dictionary,$dictionarySha),@($exe,$exeSha))) {
  if (-not (Test-Path -LiteralPath $item[0]) -or (Get-FileHash -LiteralPath $item[0] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item[1]) { throw "fingerprint differs: $($item[0])" }
}
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned native working directory absent' }
if (-not (Test-Path -LiteralPath $contract) -or -not (Test-Path -LiteralPath $builderPath) -or -not (Test-Path -LiteralPath $checkerPath) -or -not (Test-Path -LiteralPath $pythonPath)) { throw 'contract, builder, checker or Python absent' }
& $pythonPath $builderPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen G10 builder check failed' }
Write-Output 'G10.var06 native preflight: queue'
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide Issue 18 native queue busy' }
  $optionKey = 'HKCU:\Software\Systecon\SIMLOX Version 2017\Prelife Settings'
  $optionOriginal = (Get-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog).UsePrelifeLog
  Write-Output 'G10.var06 native preflight: GUI identity'
  $existing = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -le 0) { throw 'expected existing GUI PID 13340 only' }
  $guiStart = $existing[0].StartTime.ToUniversalTime().ToString('o')
  $guiSession = $existing[0].SessionId
  $sessions = @(qwinsta 2>&1)
  Write-Output 'G10.var06 native preflight: GUI session'
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
    parent_signoff = $parentSignoffSha
    parent_closure = $parentClosureSha
    donor = $donorSha
    donor_signoff = $donorSignoffSha
    manual = $manualSha
    dictionary = $dictionarySha
    contract = $contractSha
    builder = (Get-FileHash -LiteralPath $builderPath -Algorithm SHA256).Hash.ToLowerInvariant()
    checker = (Get-FileHash -LiteralPath $checkerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    python = (Get-FileHash -LiteralPath $pythonPath -Algorithm SHA256).Hash.ToLowerInvariant()
    runner_script = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    simlox_exe = $exeSha
  }
  $invocation = [ordered]@{
    schema = 'simlox-g10-var06-v100-native-candidate/ssh-cli-v1'
    case_id = 'G10'; case_version = '1.0.0-candidate'; run_id = $RunId
    created_utc = (Get-Date).ToUniversalTime().ToString('o')
    original_run_dir = $run; host_name = $env:COMPUTERNAME
    input_sha256 = $inputSha; parent_sha256 = $parentSha
    contract_sha256 = $sourceHashesBefore.contract
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
      if ($command.name -eq 'calc') {
        try {
          Set-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog -Value 'YES'
          $process = Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
        } finally {
          Set-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog -Value $optionOriginal
        }
      } else {
        $process = Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
      }
      $step.exit_code = $process.ExitCode
      Assert-Gui
      if ((Get-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog).UsePrelifeLog -ne $optionOriginal) { throw 'Prelife Log option not restored' }
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
        $log = Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw
        $marker = [regex]::Match($log, 'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
        if (-not $marker.Success) { throw 'conversion marker absent' }
        $errorCount = [int]$marker.Groups[1].Value
        $warningCount = [int]$marker.Groups[2].Value
        $noteCount = [int]$marker.Groups[3].Value
        $conversionText = $log.Substring(0, $marker.Index)
        $errorCodes = @([regex]::Matches($conversionText, '\(error #(\d+)\)') | ForEach-Object { $_.Groups[1].Value })
        $warningCodes = @([regex]::Matches($conversionText, '\(warning #(\d+)\)') | ForEach-Object { $_.Groups[1].Value })
        if ($errorCount -ne 0 -or $errorCodes.Count -ne 0) { throw "conversion errors=$errorCount codes=$($errorCodes -join ',')" }
        if ($warningCount -ne 1 -or $warningCodes.Count -ne 1 -or $warningCodes[0] -ne '108' -or $noteCount -ne 0) { throw "unreviewed conversion warnings=$warningCount codes=$($warningCodes -join ',') notes=$noteCount" }
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
  $sourceHashesAfter = [ordered]@{
    input = (Get-FileHash -LiteralPath $nativeInputPath -Algorithm SHA256).Hash.ToLowerInvariant()
    parent = (Get-FileHash -LiteralPath $parent -Algorithm SHA256).Hash.ToLowerInvariant()
    parent_signoff = (Get-FileHash -LiteralPath $parentSignoff -Algorithm SHA256).Hash.ToLowerInvariant()
    parent_closure = (Get-FileHash -LiteralPath $parentClosure -Algorithm SHA256).Hash.ToLowerInvariant()
    donor = (Get-FileHash -LiteralPath $donor -Algorithm SHA256).Hash.ToLowerInvariant()
    donor_signoff = (Get-FileHash -LiteralPath $donorSignoff -Algorithm SHA256).Hash.ToLowerInvariant()
    manual = (Get-FileHash -LiteralPath $manual -Algorithm SHA256).Hash.ToLowerInvariant()
    dictionary = (Get-FileHash -LiteralPath $dictionary -Algorithm SHA256).Hash.ToLowerInvariant()
    contract = (Get-FileHash -LiteralPath $contract -Algorithm SHA256).Hash.ToLowerInvariant()
    builder = (Get-FileHash -LiteralPath $builderPath -Algorithm SHA256).Hash.ToLowerInvariant()
    checker = (Get-FileHash -LiteralPath $checkerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    python = (Get-FileHash -LiteralPath $pythonPath -Algorithm SHA256).Hash.ToLowerInvariant()
    runner_script = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    simlox_exe = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
  }
  foreach ($key in $sourceHashesBefore.Keys) {
    if ($sourceHashesBefore[$key] -ne $sourceHashesAfter[$key]) { $errorText = "source fingerprint changed during native run: $key" }
  }
  if ((Get-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog).UsePrelifeLog -ne $optionOriginal) { $errorText = 'Prelife Log option not restored' }
  $raw = @{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File) {
    if ($file.Name -eq 'invocation.json') { continue }
    $raw[$file.Name] = [ordered]@{ bytes=$file.Length; sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
  }
  [ordered]@{ schema='simlox-g10-var06-v100-native-closure/v1'; run_id=$RunId; invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant(); source_hashes_before=$sourceHashesBefore; source_hashes_after=$sourceHashesAfter; raw=$raw; error=$errorText; scope='four_step_native_candidate'; publication_state='not_published' } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{ run_id=$RunId; run_dir=$run; native_steps='completed'; scope='four_step_native_candidate' } | ConvertTo-Json)
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

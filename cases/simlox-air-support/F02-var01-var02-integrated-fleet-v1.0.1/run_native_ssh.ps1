param([Parameter(Mandatory=$true)][ValidateSet('deterministic','risk')][string]$Arm,
      [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$run = Join-Path (Join-Path $case 'runs') $RunId
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$nativeInputPath = Join-Path $case ("$Arm-input.json")
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary = 'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$sources = [ordered]@{
  deterministic = @((Join-Path $case 'deterministic-input.json'), '2adc1eb4f40be73c0302082cef34d824e62b35e9e044af33b7af39c5f52dbb0c')
  risk = @((Join-Path $case 'risk-input.json'), '11315f8029bba6b3cebd89a7fe033fd9f220a73a2e123e943808920e1ef42534')
  contract = @((Join-Path $case 'contract.json'), 'a2616561c9d2ae755965de7684adbc9d83a810fe50b5f0171af9376b01e8e139')
  exact_diff = @((Join-Path $case 'exact-diff.json'), '294d8f9eec3ef2c2333ad8e476e92e97a0b3c8e28cb11b3158cba52b9d1f196c')
  D05 = @((Join-Path (Split-Path $case -Parent) 'D05-maintenance-competition-v1.0.0\native-input.json'), '4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad')
  F01 = @((Join-Path (Split-Path $case -Parent) 'F01-var01-two-three-level-v1.0.1\three-level-input.json'), 'ae0181581822422aaf3c8bc5b7c0352c8bf31187178408e4f211102e438c77b5')
  A04 = @((Join-Path (Split-Path $case -Parent) 'A04-two-day-formation-v1.0.0\native-input.json'), '9e2eac17e0408903e099e6ce054ebf4b91db1ca79036afe29638ee8a41d40711')
  B04 = @((Join-Path (Split-Path $case -Parent) 'B04-cross-midnight-turnround-v1.0.1\turnround-input.json'), '9f985c071d7d1958b55659f8ae39bc4c47580847d3bf6057d5e01f483004a9c5')
  C03 = @((Join-Path (Split-Path $case -Parent) 'C03-shared-crew-formation-v1.0.2\inputs\staffing-1.json'), '159f5fa91d50afbd0d15840f8f007c62a3775d02d718152004017e20e545b789')
  E04 = @((Join-Path (Split-Path $case -Parent) 'E04-upstream-transport-fast-v1.0.0\native-input.json'), '2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1')
  exe = @($exe, 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual = @($manual, '39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
  dictionary = @($dictionary, '11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0')
}
$trace = Join-Path $env:TEMP "f02-$Arm-$RunId-preflight.log"
if (Test-Path -LiteralPath $trace) { throw 'preflight trace already exists' }
function Trace([string]$stage) { Add-Content -LiteralPath $trace -Value ("{0} {1}" -f (Get-Date).ToUniversalTime().ToString('o'),$stage) -Encoding UTF8; Write-Output $stage }
Trace "F02.$Arm preflight: session and run path"
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if (Test-Path -LiteralPath $run) { throw 'immutable native run already exists' }
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned working directory absent' }
$ancestors = @()
Trace "F02.$Arm preflight: SSH ancestor"
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'cannot verify sshd ancestor' }
Trace "F02.$Arm preflight: source hashes"
foreach ($entry in $sources.GetEnumerator()) {
  $path, $expected = $entry.Value
  if (-not (Test-Path -LiteralPath $path) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw "source fingerprint differs: $($entry.Key)" }
}
Trace "F02.$Arm preflight: frozen builders"
& $python (Join-Path $case 'build.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen builder check failed' }
& $python (Join-Path $case 'describe_diff.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen diff check failed' }
$contract = Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($contract.case_id -ne 'F02' -or $contract.exact_diff_sha256 -ne $sources.exact_diff[1] -or $contract.inputs_sha256.('F02.var01_deterministic') -ne $sources.deterministic[1] -or $contract.inputs_sha256.('F02.var02_risk') -ne $sources.risk[1]) { throw 'contract fields differ' }
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
$runCreated = $false
$runSealed = $false
$fatalError = $null
try {
  Trace "F02.$Arm preflight: queue"
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide native queue busy' }
  $gui = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  Trace "F02.$Arm preflight: GUI identity"
  if ($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -le 0) { throw 'expected GUI PID 13340 only' }
  $guiSession = $gui[0].SessionId
  $guiStart = $gui[0].StartTime.ToUniversalTime().ToString('o')
  $sessions = @(qwinsta 2>&1)
  Trace "F02.$Arm preflight: GUI session"
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session not active' }
  function Assert-Gui {
    $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
    if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'GUI process changed' }
  }
  New-Item -ItemType Directory -Path $run -Force | Out-Null
  $runCreated = $true
  Trace "F02.$Arm native: run directory created"
  Copy-Item -LiteralPath $nativeInputPath -Destination (Join-Path $run 'input.json')
  $sourceHashes = [ordered]@{}
  foreach ($entry in $sources.GetEnumerator()) { $sourceHashes[$entry.Key] = $entry.Value[1] }
  foreach ($name in @('build.py','describe_diff.py','check_roundtrip.py','run_native_ssh.ps1')) {
    $sourceHashes[$name] = (Get-FileHash -LiteralPath (Join-Path $case $name) -Algorithm SHA256).Hash.ToLowerInvariant()
  }
  $sourceHashes.python = (Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant()
  $sxi = Join-Path $run 'model.sxi'; $sxo = Join-Path $run 'model.sxo'
  $commands = @(
    [pscustomobject]@{ name='import'; args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'input.json'),$sxi,(Join-Path $run 'import.log')) },
    [pscustomobject]@{ name='export'; args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'export.log')) },
    [pscustomobject]@{ name='calc'; args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log')) },
    [pscustomobject]@{ name='jsonreport'; args=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,(Join-Path $run 'report-raw.json'),(Join-Path $run 'report-export.log')) }
  )
  [ordered]@{ schema='simlox-f02-integrated-fleet-native-candidate/ssh-cli-v1'; run_id=$RunId; created_utc=(Get-Date).ToUniversalTime().ToString('o'); original_run_dir=$run; execution_mode='ssh_cli_v1'; session_id=0; ssh_ancestor_names=$ancestors; gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart}; queue_mutex='Global\SimloxIssue18NativeQueue'; working_directory=$workingDirectory; planned_commands=@($commands | ForEach-Object { [ordered]@{name=$_.name;arguments=$_.args} }); source_hashes_before=$sourceHashes; arm=$Arm; publication_state='not_published' } | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps = @(); $errorText = $null
  foreach ($command in $commands) {
    Trace "F02.$Arm native: $($command.name)"
    $step = [ordered]@{name=$command.name;arguments=$command.args;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;gui_preserved=$false;status='started';error=$null}
    $steps += $step
    try {
      Assert-Gui
      $process = Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
      $step.exit_code = $process.ExitCode
      Assert-Gui; $step.gui_preserved = $true
      if ($process.ExitCode -ne 0) { throw "$($command.name) exit=$($process.ExitCode)" }
      $required = switch ($command.name) { 'import' {@('model.sxi','import.log')} 'export' {@('roundtrip-raw.json','export.log')} 'calc' {@('model.sxo','run.log','model.log')} 'jsonreport' {@('report-raw.json','report-export.log')} }
      foreach ($name in $required) { $path = Join-Path $run $name; if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -le 4) { throw "$($command.name) output $name absent/empty" } }
      if ($command.name -eq 'calc') {
        $log = Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw -Encoding UTF8
        if ($log -notmatch 'Input conversion completed\. Errors: 0, Warnings:') { throw 'converter errors or completion marker absent' }
      }
      $step.status = 'completed'
    } catch { $errorText = $_.Exception.Message; $step.status='failed'; $step.error=$errorText; break }
    finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
  }
  if (Test-Path -LiteralPath (Join-Path $run 'roundtrip-raw.json')) {
    $step = [ordered]@{name='check_import_export';started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;status='started';error=$null}
    $steps += $step
    try {
      & $python (Join-Path $case 'check_roundtrip.py') $run | Set-Content -LiteralPath (Join-Path $run 'roundtrip-validation.json') -Encoding UTF8
      $step.exit_code = $LASTEXITCODE
      Assert-Gui
      if ($step.exit_code -ne 0) { throw "roundtrip checker exit=$($step.exit_code)" }
      $step.status='completed'
    } catch { if (-not $errorText) { $errorText=$_.Exception.Message }; $step.status='failed'; $step.error=$_.Exception.Message }
    finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
  }
  $sourceHashesAfter = [ordered]@{}
  foreach ($entry in $sources.GetEnumerator()) { $sourceHashesAfter[$entry.Key] = (Get-FileHash -LiteralPath $entry.Value[0] -Algorithm SHA256).Hash.ToLowerInvariant() }
  foreach ($name in @('build.py','describe_diff.py','check_roundtrip.py','run_native_ssh.ps1')) { $sourceHashesAfter[$name] = (Get-FileHash -LiteralPath (Join-Path $case $name) -Algorithm SHA256).Hash.ToLowerInvariant() }
  $sourceHashesAfter.python = (Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant()
  foreach ($key in $sourceHashes.Keys) { if ($sourceHashes[$key] -ne $sourceHashesAfter[$key]) { $errorText = "source changed during run: $key" } }
  $raw = @{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File) { if ($file.Name -ne 'invocation.json') { $raw[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} } }
  [ordered]@{schema='simlox-f02-integrated-fleet-native-closure/v1';run_id=$RunId;invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();source_hashes_before=$sourceHashes;source_hashes_after=$sourceHashesAfter;raw=$raw;error=$errorText;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $runSealed = $true
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;native_steps='completed'} | ConvertTo-Json)
} catch {
  $fatalError = $_.Exception.Message
  throw
} finally {
  if ($runCreated -and -not $runSealed -and -not (Test-Path -LiteralPath (Join-Path $run 'closure.json'))) {
    try {
      $partialRaw = @{}
      foreach ($file in Get-ChildItem -LiteralPath $run -File) {
        if ($file.Name -ne 'invocation.json') { $partialRaw[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} }
      }
      $invocationPath = Join-Path $run 'invocation.json'
      $invocationSha = if (Test-Path -LiteralPath $invocationPath) { (Get-FileHash -LiteralPath $invocationPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
      [ordered]@{schema='simlox-f02-integrated-fleet-native-closure/v1';run_id=$RunId;invocation_sha256=$invocationSha;source_hashes_before=$sourceHashes;source_hashes_after=$null;raw=$partialRaw;error=$fatalError;publication_state='excluded_diagnostic';partial=$true} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
    } catch { Write-Error "partial closure failed: $($_.Exception.Message)" }
  }
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

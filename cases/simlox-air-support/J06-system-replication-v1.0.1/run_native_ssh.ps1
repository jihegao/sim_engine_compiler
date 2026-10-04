param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$run = Join-Path (Join-Path $case 'runs') $RunId
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$nativeInputPath = Join-Path $case 'replication-input.json'
$parentDir = Join-Path (Split-Path $case -Parent) 'J04-var01-fixed-replications-v1.0.0'
$precedentDir = Join-Path (Split-Path $case -Parent) 'J05-profile-snapshot-v1.0.1'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary = 'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$defaultSettings = 'C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs'
& $python (Join-Path $case 'make_report_settings.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'settings builder failed' }
$settings = Join-Path $case 'runs\report-settings\replications-enabled.sxs'
$sources = [ordered]@{
  input = @((Join-Path $case 'replication-input.json'), '60d34ec2679a72895f0378d7bb8cffec71bc2bc969a198c6227349b66c338258')
  parent = @((Join-Path $parentDir 'probe-input.json'), '4a4e2df598a515762b1c4de8894c139c6ac6bce40c523d7e5f0720514f7f5579')
  parent_closure = @((Join-Path $parentDir 'runs\j04-var01-fixed-reps-accepted-20261001-03\closure.json'), 'e3744088bc407bc5ca58c2ad7c975a10662d32f5b72afdc8a227c4a4c310f6a5')
  parent_signoff = @((Join-Path $parentDir 'cli-scope-signoff-2026-10-01.md'), 'f2ab35cd6b5daf411bf10106ced33dc66208546d6984aa2f1dcb5a1ebfe9445b')
  precedent_signoff = @((Join-Path $precedentDir 'cli-scope-signoff-2026-10-01.md'), '61e119b8a8980293e5e2e19751c6ff4744164dfd9e2d5f1b2163704fddeb5888')
  contract = @((Join-Path $case 'contract.json'), '57655fa7ebbcbe563efd4d256bcee0dffa09e93a624624d97109ed970be75610')
  exact_diff = @((Join-Path $case 'exact-diff.json'), 'afffa6e3cefb077f447374b1e25a158eb757c0473b6bb425f7dcaed7e30029b8')
  exe = @($exe, 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual = @($manual, '39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
  dictionary = @($dictionary, '11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0')
  default_settings = @($defaultSettings, '1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d')
  report_settings = @($settings, '6417a4f4ece02e758b4cae90afb674ec93d3c0b3aa730bdb6334df036d746882')
  excluded_closure = @((Join-Path (Split-Path $case -Parent) 'J06-system-replication-percentile-v1.0.0\runs\j06-system-replication-v100-ssh-20261004-01\closure.json'), '994f700c6917ed3b887d0c88259381f1c4727c4e10e563a7c3d060badebd04c8')
}
$trace = Join-Path $env:TEMP "j06-replication-$RunId-preflight.log"
if (Test-Path -LiteralPath $trace) { throw 'preflight trace already exists' }
function Trace([string]$stage) { Add-Content -LiteralPath $trace -Value ("{0} {1}" -f (Get-Date).ToUniversalTime().ToString('o'),$stage) -Encoding UTF8; Write-Output $stage }
Trace "J06.var02 preflight: session and run path"
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if (Test-Path -LiteralPath $run) { throw 'immutable native run already exists' }
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned working directory absent' }
$ancestors = @()
Trace "J06.var02 preflight: SSH ancestor"
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'cannot verify sshd ancestor' }
Trace "J06.var02 preflight: source hashes"
foreach ($entry in $sources.GetEnumerator()) {
  $path, $expected = $entry.Value
  if (-not (Test-Path -LiteralPath $path) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw "source fingerprint differs: $($entry.Key)" }
}
Trace "J06.var02 preflight: frozen builders"
& $python (Join-Path $case 'build.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen builder check failed' }
& $python (Join-Path $case 'describe_diff.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen diff check failed' }
$contract = Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($contract.case_id -ne 'J06' -or $contract.variant_id -ne 'J06.var02' -or $contract.child_input_sha256 -ne $sources.input[1] -or $contract.exact_diff_sha256 -ne $sources.exact_diff[1] -or $contract.accepted_parent.input_sha256 -ne $sources.parent[1] -or $contract.accepted_parent.closure_sha256 -ne $sources.parent_closure[1] -or $contract.accepted_parent.signoff_sha256 -ne $sources.parent_signoff[1] -or $contract.report_precedent.signoff_sha256 -ne $sources.precedent_signoff[1] -or $contract.report_precedent.installed_default_settings_sha256 -ne $sources.default_settings[1] -or $contract.report_precedent.one_byte_outpr_enabled_sha256 -ne $sources.report_settings[1] -or $contract.excluded_diagnostic.closure_sha256 -ne $sources.excluded_closure[1] -or $contract.parameters.nreps -ne 16) { throw 'contract fields differ' }
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
$runCreated = $false
$runSealed = $false
$fatalError = $null
try {
  Trace "J06.var02 preflight: queue"
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide native queue busy' }
  $gui = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  Trace "J06.var02 preflight: GUI identity"
  if ($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -le 0) { throw 'expected GUI PID 13340 only' }
  $guiSession = $gui[0].SessionId
  $guiStart = $gui[0].StartTime.ToUniversalTime().ToString('o')
  $sessions = @(qwinsta 2>&1)
  Trace "J06.var02 preflight: GUI session"
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session not active' }
  function Assert-Gui {
    $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
    if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'GUI process changed' }
  }
  New-Item -ItemType Directory -Path $run -Force | Out-Null
  $runCreated = $true
  Trace "J06.var02 native: run directory created"
  Copy-Item -LiteralPath $nativeInputPath -Destination (Join-Path $run 'input.json')
  $sourceHashes = [ordered]@{}
  foreach ($entry in $sources.GetEnumerator()) { $sourceHashes[$entry.Key] = $entry.Value[1] }
  foreach ($name in @('build.py','describe_diff.py','make_report_settings.py','check_roundtrip.py','run_native_ssh.ps1')) {
    $sourceHashes[$name] = (Get-FileHash -LiteralPath (Join-Path $case $name) -Algorithm SHA256).Hash.ToLowerInvariant()
  }
  $sourceHashes.python = (Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant()
  $sxi = Join-Path $run 'model.sxi'; $sxo = Join-Path $run 'model.sxo'
  $commands = @(
    [pscustomobject]@{ name='import'; args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'input.json'),$sxi,(Join-Path $run 'import.log')) },
    [pscustomobject]@{ name='export'; args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'export.log')) },
    [pscustomobject]@{ name='calc'; args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log')) },
    [pscustomobject]@{ name='jsonreport'; args=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,(Join-Path $run 'report-raw.json'),(Join-Path $run 'report-export.log')) },
    [pscustomobject]@{ name='replication_report'; args=('"{0}" -silent -report -rpts "{1}" -rjexport "{2}" -log "{3}" -close' -f $sxo,$settings,(Join-Path $run 'replication-report-raw.json'),(Join-Path $run 'replication-report-export.log')) }
  )
  [ordered]@{ schema='simlox-j06-replication-native-candidate/ssh-cli-v1'; run_id=$RunId; created_utc=(Get-Date).ToUniversalTime().ToString('o'); original_run_dir=$run; execution_mode='ssh_cli_v1'; session_id=0; ssh_ancestor_names=$ancestors; gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart}; queue_mutex='Global\SimloxIssue18NativeQueue'; working_directory=$workingDirectory; planned_commands=@($commands | ForEach-Object { [ordered]@{name=$_.name;arguments=$_.args} }); source_hashes_before=$sourceHashes; publication_state='not_published' } | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps = @(); $errorText = $null
  foreach ($command in $commands) {
    Trace "J06.var02 native: $($command.name)"
    $step = [ordered]@{name=$command.name;arguments=$command.args;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;gui_preserved=$false;status='started';error=$null}
    $steps += $step
    try {
      Assert-Gui
      $process = Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
      $step.exit_code = $process.ExitCode
      Assert-Gui; $step.gui_preserved = $true
      if ($process.ExitCode -ne 0) { throw "$($command.name) exit=$($process.ExitCode)" }
      $required = switch ($command.name) { 'import' {@('model.sxi','import.log')} 'export' {@('roundtrip-raw.json','export.log')} 'calc' {@('model.sxo','run.log','model.log')} 'jsonreport' {@('report-raw.json','report-export.log')} 'replication_report' {@('replication-report-raw.json','replication-report-export.log')} }
      foreach ($name in $required) { $path = Join-Path $run $name; if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -le 4) { throw "$($command.name) output $name absent/empty" } }
      if ($command.name -eq 'calc') {
        $log = Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw -Encoding UTF8
        if ($log -notmatch 'Input conversion completed\. Errors: 0, Warnings: 3, Notes: 0' -or ([regex]::Matches($log,'\(warning #108\)')).Count -ne 1 -or ([regex]::Matches($log,'\(warning #126\)')).Count -ne 1 -or ([regex]::Matches($log,'\(warning #211\)')).Count -ne 1 -or $log -match '\((?:warning|notice) #(?!(?:108|126|211)\))') { throw 'unexpected converter diagnostic set' }
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
      $roundtrip = Get-Content -LiteralPath (Join-Path $run 'roundtrip-validation.json') -Raw -Encoding UTF8 | ConvertFrom-Json
      if ($roundtrip.passed -ne $true) { throw 'roundtrip checker did not pass' }
      $step.status='completed'
    } catch { if (-not $errorText) { $errorText=$_.Exception.Message }; $step.status='failed'; $step.error=$_.Exception.Message }
    finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
  }
  $sourceHashesAfter = [ordered]@{}
  foreach ($entry in $sources.GetEnumerator()) { $sourceHashesAfter[$entry.Key] = (Get-FileHash -LiteralPath $entry.Value[0] -Algorithm SHA256).Hash.ToLowerInvariant() }
  foreach ($name in @('build.py','describe_diff.py','make_report_settings.py','check_roundtrip.py','run_native_ssh.ps1')) { $sourceHashesAfter[$name] = (Get-FileHash -LiteralPath (Join-Path $case $name) -Algorithm SHA256).Hash.ToLowerInvariant() }
  $sourceHashesAfter.python = (Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant()
  foreach ($key in $sourceHashes.Keys) { if ($sourceHashes[$key] -ne $sourceHashesAfter[$key]) { $errorText = "source changed during run: $key" } }
  $raw = @{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File) { if ($file.Name -ne 'invocation.json') { $raw[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} } }
  [ordered]@{schema='simlox-j06-replication-native-closure/v1';run_id=$RunId;invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();source_hashes_before=$sourceHashes;source_hashes_after=$sourceHashesAfter;raw=$raw;error=$errorText;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
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
      [ordered]@{schema='simlox-j06-replication-native-closure/v1';run_id=$RunId;invocation_sha256=$invocationSha;source_hashes_before=$sourceHashes;source_hashes_after=$null;raw=$partialRaw;error=$fatalError;publication_state='excluded_diagnostic';partial=$true} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
    } catch { Write-Error "partial closure failed: $($_.Exception.Message)" }
  }
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

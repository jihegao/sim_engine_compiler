param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$run = Join-Path (Join-Path $case 'runs') $RunId
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$nativeInputPath = Join-Path $case 'repair-input.json'
$parentDir = Join-Path (Split-Path $case -Parent) 'F02-var01-var02-integrated-fleet-v1.0.2'
$siblingDir = Join-Path (Split-Path $case -Parent) 'F02-var04-terminal-active-v1.0.2'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary = 'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$sources = [ordered]@{
  input = @((Join-Path $case 'repair-input.json'), '7605c2a22396cc9d7962c96ede757b93b11c94e01480ed625fdfd63f359297ce')
  parent = @((Join-Path $parentDir 'risk-input.json'), 'ae46b08a6ef6fd063906b888fb3c73fba06edcb57acc1a4ade49fc62c53fd7d3')
  parent_closure = @((Join-Path $parentDir 'runs\f02-pair-v102-risk-ssh-20261004-01\closure.json'), 'b82da3cbed601408e4a72cda5c2fd498286a8f1b3ebfa07c003d4d4f8e6c91c4')
  parent_evidence_index = @((Join-Path $parentDir 'evidence-index.json'), 'a6c704eefc00c544be0ef54ca4487ebe27b99258130d6650d3923c17421fc906')
  sibling_index = @((Join-Path $siblingDir 'evidence-index.json'), 'e49132c7c9310b2162efc014fc63dd51edfae2c7cbf9a457dede118a2008bc0e')
  sibling_closure = @((Join-Path $siblingDir 'runs\f02-var04-terminal-v102-ssh-20261004-01\closure.json'), 'ebceedbeab4b63309b964fe1b5db40fdbd0d5459a65e2188ed8e1b80c6c91765')
  contract = @((Join-Path $case 'contract.json'), 'b4f217b17d44bb83eeda84887c1a1509b0e059ce212d580443afebba7286b2c9')
  exact_diff = @((Join-Path $case 'exact-diff.json'), 'b63e01f862ee651aa959a66a75e339875b3f65a14a0f901c448630d95dd97e8b')
  exe = @($exe, 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual = @($manual, '39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
  dictionary = @($dictionary, '11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0')
}
$trace = Join-Path $env:TEMP "f02-var04-repair-$RunId-preflight.log"
if (Test-Path -LiteralPath $trace) { throw 'preflight trace already exists' }
function Trace([string]$stage) { Add-Content -LiteralPath $trace -Value ("{0} {1}" -f (Get-Date).ToUniversalTime().ToString('o'),$stage) -Encoding UTF8; Write-Output $stage }
Trace "F02.var04 preflight: session and run path"
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if (Test-Path -LiteralPath $run) { throw 'immutable native run already exists' }
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned working directory absent' }
$ancestors = @()
Trace "F02.var04 preflight: SSH ancestor"
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'cannot verify sshd ancestor' }
Trace "F02.var04 preflight: source hashes"
foreach ($entry in $sources.GetEnumerator()) {
  $path, $expected = $entry.Value
  if (-not (Test-Path -LiteralPath $path) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw "source fingerprint differs: $($entry.Key)" }
}
Trace "F02.var04 preflight: frozen builders"
& $python (Join-Path $case 'build.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen builder check failed' }
& $python (Join-Path $case 'describe_diff.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen diff check failed' }
$contract = Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($contract.case_id -ne 'F02' -or $contract.variant_id -ne 'F02.var04' -or $contract.repair_input_sha256 -ne $sources.input[1] -or $contract.exact_diff_sha256 -ne $sources.exact_diff[1] -or $contract.accepted_parent.input_sha256 -ne $sources.parent[1] -or $contract.accepted_parent.closure_sha256 -ne $sources.parent_closure[1] -or $contract.accepted_parent.evidence_index_sha256 -ne $sources.parent_evidence_index[1] -or $contract.accepted_sibling.evidence_index_sha256 -ne $sources.sibling_index[1] -or $contract.accepted_sibling.native_closure_sha256 -ne $sources.sibling_closure[1]) { throw 'contract fields differ' }
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
$runCreated = $false
$runSealed = $false
$fatalError = $null
try {
  Trace "F02.var04 preflight: queue"
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide native queue busy' }
  $gui = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  Trace "F02.var04 preflight: GUI identity"
  if ($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -le 0) { throw 'expected GUI PID 13340 only' }
  $guiSession = $gui[0].SessionId
  $guiStart = $gui[0].StartTime.ToUniversalTime().ToString('o')
  $sessions = @(qwinsta 2>&1)
  Trace "F02.var04 preflight: GUI session"
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session not active' }
  function Assert-Gui {
    $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
    if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'GUI process changed' }
  }
  New-Item -ItemType Directory -Path $run -Force | Out-Null
  $runCreated = $true
  Trace "F02.var04 native: run directory created"
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
  [ordered]@{ schema='simlox-f02-var04-active-repair-native-candidate/ssh-cli-v1'; run_id=$RunId; created_utc=(Get-Date).ToUniversalTime().ToString('o'); original_run_dir=$run; execution_mode='ssh_cli_v1'; session_id=0; ssh_ancestor_names=$ancestors; gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart}; queue_mutex='Global\SimloxIssue18NativeQueue'; working_directory=$workingDirectory; planned_commands=@($commands | ForEach-Object { [ordered]@{name=$_.name;arguments=$_.args} }); source_hashes_before=$sourceHashes; publication_state='not_published' } | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps = @(); $errorText = $null
  foreach ($command in $commands) {
    Trace "F02.var04 native: $($command.name)"
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
        if ($log -notmatch 'Input conversion completed\. Errors: 0, Warnings: 1, Notes: 0' -or ([regex]::Matches($log,'\(warning #108\)')).Count -ne 1 -or $log -match '\((?:warning|notice) #(?!(?:108)\))') { throw 'unexpected converter diagnostic set' }
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
  [ordered]@{schema='simlox-f02-var04-active-repair-native-closure/v1';run_id=$RunId;invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();source_hashes_before=$sourceHashes;source_hashes_after=$sourceHashesAfter;raw=$raw;error=$errorText;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
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
      [ordered]@{schema='simlox-f02-var04-active-repair-native-closure/v1';run_id=$RunId;invocation_sha256=$invocationSha;source_hashes_before=$sourceHashes;source_hashes_after=$null;raw=$partialRaw;error=$fatalError;publication_state='excluded_diagnostic';partial=$true} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
    } catch { Write-Error "partial closure failed: $($_.Exception.Message)" }
  }
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

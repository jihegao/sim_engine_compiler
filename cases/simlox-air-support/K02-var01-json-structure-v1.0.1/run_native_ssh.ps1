param([Parameter(Mandatory=$true)][ValidateSet('inactive2','named')][string]$Arm,
      [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$run = Join-Path (Join-Path $case 'runs') $RunId
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$nativeInputPath = Join-Path $case "$Arm-input.json"
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary = 'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$sources = [ordered]@{
  inactive2_input = @((Join-Path $case 'inactive2-input.json'), '0614e3cb935b519369197b3d3ee4991a28c25cb80b6f9a593615a12fa85f0389')
  named_input = @((Join-Path $case 'named-input.json'), 'b94e367d46665d4d58f2fb8d15771a61a6d51369070db85ab9bda851c3e76b00')
  contract = @((Join-Path $case 'contract.json'), 'd70b9c8e6bca44acd87128d46d56da3099b5da825d98722717531d07ea4dba44')
  exact_diff = @((Join-Path $case 'exact-diff.json'), '84d49ecea6c7651300bb479b95b641a77d554014bba50c43f7026d2e480b2665')
  accepted_parent = @((Join-Path (Split-Path $case -Parent) 'K01-var04-parent-child-model-diff-v1.0.0\native-input.json'), 'd1ff80f7e0de8259b6f38b6373c7ad4797d897e17c4397a7060dfbefbeb851dc')
  accepted_parent_closure = @((Join-Path (Split-Path $case -Parent) 'K01-var04-parent-child-model-diff-v1.0.0\runs\k01-var04-duration-v100-ssh-20261004-01\closure.json'), '5200cc3f73c3dfce1b89f61314a0d98e460c4a9a08888139da0e3f8e3baa2b10')
  accepted_parent_signoff = @((Join-Path (Split-Path $case -Parent) 'K01-var04-parent-child-model-diff-v1.0.0\cli-scope-signoff-2026-10-04.md'), 'a1413b52002bf34919cf594ad6a5c076dc864a61018e87abc7265c3fe27412ca')
  accepted_parent_report = @((Join-Path (Split-Path $case -Parent) 'K01-var04-parent-child-model-diff-v1.0.0\runs\k01-var04-duration-v100-ssh-20261004-01\report-raw.json'), 'da806aee7886132cc6dda6bbf89b3f7ba9603c0a90ae45be5466e18b3a28de4c')
  accepted_parent_log = @((Join-Path (Split-Path $case -Parent) 'K01-var04-parent-child-model-diff-v1.0.0\runs\k01-var04-duration-v100-ssh-20261004-01\model.log'), '2d2e6c368305203052e347748dab8f36261947dae6f6a189fad4312e47c0a491')
  exe = @($exe, 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual = @($manual, '39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
  dictionary = @($dictionary, '11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0')
}
$trace = Join-Path $env:TEMP "k02-var01-v101-$Arm-$RunId-preflight.log"
if (Test-Path -LiteralPath $trace) { throw 'preflight trace already exists' }
function Trace([string]$stage) { Add-Content -LiteralPath $trace -Value ("{0} {1}" -f (Get-Date).ToUniversalTime().ToString('o'),$stage) -Encoding UTF8; Write-Output $stage }
Trace "K02.var01 $Arm preflight: session and run path"
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if (Test-Path -LiteralPath $run) { throw 'immutable native run already exists' }
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned working directory absent' }
$ancestors = @()
Trace "K02.var01 $Arm preflight: SSH ancestor"
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'cannot verify sshd ancestor' }
Trace "K02.var01 $Arm preflight: source hashes"
foreach ($entry in $sources.GetEnumerator()) {
  $path, $expected = $entry.Value
  if (-not (Test-Path -LiteralPath $path) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw "source fingerprint differs: $($entry.Key)" }
}
Trace "K02.var01 $Arm preflight: frozen builder"
& $python (Join-Path $case 'build.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen builder check failed' }
$contract = Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($contract.case_id -ne 'K02' -or $contract.variant_id -ne 'K02.var01' -or $contract.version -ne '1.0.1-candidate' -or $contract.publication_state -ne 'not_published' -or $contract.inputs_sha256.inactive2 -ne $sources.inactive2_input[1] -or $contract.inputs_sha256.named -ne $sources.named_input[1] -or $contract.accepted_parent.input_sha256 -ne $sources.accepted_parent[1] -or $contract.accepted_parent.closure_sha256 -ne $sources.accepted_parent_closure[1] -or $contract.parameters.nreps -ne 1 -or $contract.parameters.seed -ne 1 -or $contract.parameters.horizon_hours -ne 36 -or $contract.parameters.mission_duration_hours -ne 3) { throw 'contract fields differ' }
if ($contract.expected_converter.errors -ne 0 -or $contract.expected_converter.warnings -ne 2 -or $contract.expected_converter.notes -ne 0 -or ($contract.expected_converter.warning_codes_in_order -join ',') -ne '108,126') { throw 'converter contract differs' }
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
$runCreated = $false
$runSealed = $false
$fatalError = $null
try {
  Trace "K02.var01 $Arm preflight: queue"
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide native queue busy' }
  $gui = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  Trace "K02.var01 $Arm preflight: GUI identity"
  if ($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -le 0) { throw 'expected GUI PID 13340 only' }
  $guiSession = $gui[0].SessionId
  $guiStart = $gui[0].StartTime.ToUniversalTime().ToString('o')
  $sessions = @(qwinsta 2>&1)
  Trace "K02.var01 $Arm preflight: GUI session"
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session not active' }
  function Assert-Gui {
    $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
    if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'GUI process changed' }
  }
  New-Item -ItemType Directory -Path $run -Force | Out-Null
  $runCreated = $true
  Trace "K02.var01 $Arm native: run directory created"
  Copy-Item -LiteralPath $nativeInputPath -Destination (Join-Path $run 'input.json')
  $sourceHashes = [ordered]@{}
  foreach ($entry in $sources.GetEnumerator()) { $sourceHashes[$entry.Key] = $entry.Value[1] }
  foreach ($name in @('build.py','check_roundtrip.py','run_native_ssh.ps1')) {
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
  [ordered]@{ schema='simlox-k02-var01-native/ssh-cli-v1'; arm=$Arm; run_id=$RunId; created_utc=(Get-Date).ToUniversalTime().ToString('o'); original_run_dir=$run; execution_mode='ssh_cli_v1'; session_id=0; ssh_ancestor_names=$ancestors; gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart}; queue_mutex='Global\SimloxIssue18NativeQueue'; working_directory=$workingDirectory; planned_commands=@($commands | ForEach-Object { [ordered]@{name=$_.name;arguments=$_.args} }); source_hashes_before=$sourceHashes; publication_state='not_published' } | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps = @(); $errorText = $null
  foreach ($command in $commands) {
    Trace "K02.var01 $Arm native: $($command.name)"
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
        $warningCodes = @([regex]::Matches($log, '\(warning #(\d+)\)') | ForEach-Object { $_.Groups[1].Value })
        if ($log -notmatch 'Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0' -or
            ($warningCodes -join ',') -ne '108,126' -or
            $log -notmatch 'rec 1: \(warning #126\) This system contains no items: TEACH-AIR-01' -or
            [regex]::IsMatch($log, '\((?:error|notice) #')) {
          throw 'unexpected converter diagnostic'
        }
      }
      $step.status = 'completed'
    } catch { $errorText = $_.Exception.Message; $step.status='failed'; $step.error=$errorText; break }
    finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
  }
  if (Test-Path -LiteralPath (Join-Path $run 'roundtrip-raw.json')) {
    $step = [ordered]@{name='check_import_export';started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;status='started';error=$null}
    $steps += $step
    try {
      & $python (Join-Path $case 'check_roundtrip.py') $Arm $run | Set-Content -LiteralPath (Join-Path $run 'roundtrip-validation.json') -Encoding UTF8
      $step.exit_code = $LASTEXITCODE
      Assert-Gui
      if ($step.exit_code -ne 0) { throw "roundtrip checker exit=$($step.exit_code)" }
      $step.status='completed'
    } catch { if (-not $errorText) { $errorText=$_.Exception.Message }; $step.status='failed'; $step.error=$_.Exception.Message }
    finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
  }
  $sourceHashesAfter = [ordered]@{}
  foreach ($entry in $sources.GetEnumerator()) { $sourceHashesAfter[$entry.Key] = (Get-FileHash -LiteralPath $entry.Value[0] -Algorithm SHA256).Hash.ToLowerInvariant() }
  foreach ($name in @('build.py','check_roundtrip.py','run_native_ssh.ps1')) { $sourceHashesAfter[$name] = (Get-FileHash -LiteralPath (Join-Path $case $name) -Algorithm SHA256).Hash.ToLowerInvariant() }
  $sourceHashesAfter.python = (Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant()
  foreach ($key in $sourceHashes.Keys) { if ($sourceHashes[$key] -ne $sourceHashesAfter[$key]) { $errorText = "source changed during run: $key" } }
  $raw = @{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File) { if ($file.Name -ne 'invocation.json') { $raw[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} } }
  [ordered]@{schema='simlox-k02-var01-native-closure/v1';arm=$Arm;run_id=$RunId;invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();source_hashes_before=$sourceHashes;source_hashes_after=$sourceHashesAfter;raw=$raw;error=$errorText;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
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
      [ordered]@{schema='simlox-k02-var01-native-closure/v1';arm=$Arm;run_id=$RunId;invocation_sha256=$invocationSha;source_hashes_before=$sourceHashes;source_hashes_after=$null;raw=$partialRaw;error=$fatalError;publication_state='excluded_diagnostic';partial=$true} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
    } catch { Write-Error "partial closure failed: $($_.Exception.Message)" }
  }
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

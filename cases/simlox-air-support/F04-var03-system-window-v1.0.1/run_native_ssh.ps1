param([Parameter(Mandatory=$true)][ValidateSet('system')][string]$Arm,
      [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$run = Join-Path (Join-Path $case 'runs') $RunId
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$nativeInputPath = Join-Path $case 'native-input.json'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary = 'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
& $python (Join-Path $case 'make_report_settings.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'settings builder failed' }
$defaultSettings = 'C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs'
$settings = Join-Path $case 'runs\report-settings\replications-enabled.sxs'
$sources = [ordered]@{
  native_input = @((Join-Path $case 'native-input.json'), '30875386d868448b9fb8beaa4ad1c6da0f77f3d6b22eb7def2d09f12116f3aa7')
  contract = @((Join-Path $case 'contract.json'), 'd70fa66ab6a96b08fa60350be7b33626d7dcc819bf462d75506c081e9812475f')
  exact_diff = @((Join-Path $case 'exact-diff.json'), 'dcab03323054a12be458efd93c8aa306c5dfcbf02a58a4aff9dee11dd7f90b95')
  accepted_parent = @((Join-Path (Split-Path $case -Parent) 'F04-var02-stochastic-43day-v1.0.0\native-input.json'), '33ec12ae0e576969673bcb0e9ccb2ade9bb3799b91e13d734e77950941645cb4')
  accepted_parent_closure = @((Join-Path (Split-Path $case -Parent) 'F04-var02-stochastic-43day-v1.0.0\runs\f04-var02-stochastic-v100-repeat-a-ssh-20261004-01\closure.json'), 'e61172db53cbaf56555ee1be7585284e5e709a72490c0a5d3306fb0da13f8be9')
  accepted_parent_signoff = @((Join-Path (Split-Path $case -Parent) 'F04-var02-stochastic-43day-v1.0.0\cli-scope-signoff-2026-10-04.md'), 'e38bf286a62c72ea759869243791bb357003533e82009b9736cc134df7e974d8')
  accepted_parent_report = @((Join-Path (Split-Path $case -Parent) 'F04-var02-stochastic-43day-v1.0.0\runs\f04-var02-stochastic-v100-repeat-a-ssh-20261004-01\report-raw.json'), 'cce8e62b965bac8c05e17dc3de97361561e9fcf02ba40fef34ee69ad786725be')
  accepted_parent_replication_report = @((Join-Path (Split-Path $case -Parent) 'F04-var02-stochastic-43day-v1.0.0\runs\f04-var02-stochastic-v100-repeat-a-ssh-20261004-01\replication-report-raw.json'), '0bf434c097baf63aedcf5dcac29932d3cec6e4f4453f3aaccc4fc4be986aae27')
  excluded_diagnostic_input = @((Join-Path (Split-Path $case -Parent) 'F04-var03-first-cycle-window-v1.0.0\native-input.json'), 'a5c05a7dca62093cad49d1f79f135c8c305ef1103d50fb7044309b18e15ff252')
  excluded_diagnostic_closure = @((Join-Path (Split-Path $case -Parent) 'F04-var03-first-cycle-window-v1.0.0\runs\f04-var03-first-cycle-v100-ssh-20261004-01\closure.json'), '1a7dc233fbe335e1abba3dfc204c1dbfa040434861c9888ed118c9aa472fd0f5')
  default_settings = @($defaultSettings, '1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d')
  report_settings = @($settings, '6417a4f4ece02e758b4cae90afb674ec93d3c0b3aa730bdb6334df036d746882')
  J04_signoff = @((Join-Path (Split-Path $case -Parent) 'J04-var01-fixed-replications-v1.0.0\cli-scope-signoff-2026-10-01.md'), 'f2ab35cd6b5daf411bf10106ced33dc66208546d6984aa2f1dcb5a1ebfe9445b')
  J05_signoff = @((Join-Path (Split-Path $case -Parent) 'J05-horizon-v1.0.0\cli-scope-signoff-2026-10-01.md'), 'f8a9bb725fcb58cabb0a4e4e58450a7da00656c97becd9e3f7bd88c954de14b3')
  J06_signoff = @((Join-Path (Split-Path $case -Parent) 'J06-system-replication-v1.0.1\cli-scope-signoff-2026-10-04.md'), '7781fccac86c1e0b85ed659145c42bd724ccb0b7c509cd711f4437a146e7219d')
  J07_signoff = @((Join-Path (Split-Path $case -Parent) 'J07-formation-denial-v1.0.0\cli-scope-signoff-2026-10-01.md'), 'a798630687c5d59026cedef40b2aa1f1399c9b59c6545bf2c870252512759c94')
  J08_signoff = @((Join-Path (Split-Path $case -Parent) 'J08-item-stock-resource-ledger-v1.0.0\cli-scope-signoff-2026-10-04.md'), 'c57d20337693846694a5385f196af5b1eb3407e55f9bb1e87b72f3afb5f15421')
  A17_input = @((Join-Path (Split-Path $case -Parent) 'A17-multi-unit-group-v1.0.0\native-input.json'), '66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974')
  A17_signoff = @((Join-Path (Split-Path $case -Parent) 'A17-multi-unit-group-v1.0.0\cli-scope-signoff-2026-09-29.md'), '77d204b5ca22222d1331051a68bb9c4fad2f50fc6ee94134d32d047dd5105e40')
  E07_signoff = @((Join-Path (Split-Path $case -Parent) 'E07-item-specific-transport-v1.0.1\cli-scope-signoff-2026-10-01.md'), 'f0683a30a42aa101c4c88ac242d7d6b1d38857dfc56f650cce0bab44323120fc')
  I01_signoff = @((Join-Path (Split-Path $case -Parent) 'I01-var01-resource-points-v1.0.0\cli-scope-signoff-2026-10-02.md'), 'e0ab772da4b2fbaf707f9df3c0d7e40afad0f19bf55ede690e4efaf77762946c')
  exe = @($exe, 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual = @($manual, '39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
  dictionary = @($dictionary, '11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0')
}
$trace = Join-Path $env:TEMP "f04-$Arm-$RunId-preflight.log"
if (Test-Path -LiteralPath $trace) { throw 'preflight trace already exists' }
function Trace([string]$stage) { Add-Content -LiteralPath $trace -Value ("{0} {1}" -f (Get-Date).ToUniversalTime().ToString('o'),$stage) -Encoding UTF8; Write-Output $stage }
Trace "F04.$Arm preflight: session and run path"
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if (Test-Path -LiteralPath $run) { throw 'immutable native run already exists' }
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned working directory absent' }
$ancestors = @()
Trace "F04.$Arm preflight: SSH ancestor"
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'cannot verify sshd ancestor' }
Trace "F04.$Arm preflight: source hashes"
foreach ($entry in $sources.GetEnumerator()) {
  $path, $expected = $entry.Value
  if (-not (Test-Path -LiteralPath $path) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw "source fingerprint differs: $($entry.Key)" }
}
Trace "F04.$Arm preflight: frozen builders"
& $python (Join-Path $case 'build.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen builder check failed' }
& $python (Join-Path $case 'describe_diff.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen diff check failed' }
$contract = Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($contract.case_id -ne 'F04' -or $contract.variant_id -ne 'F04.var03' -or $contract.version -ne '1.0.1-candidate' -or $contract.publication_state -ne 'not_published' -or $contract.exact_diff_sha256 -ne $sources.exact_diff[1] -or $contract.input_sha256 -ne $sources.native_input[1] -or $contract.accepted_parent.input_sha256 -ne $sources.accepted_parent[1] -or $contract.accepted_parent.closure_sha256 -ne $sources.accepted_parent_closure[1] -or $contract.accepted_parent.signoff_sha256 -ne $sources.accepted_parent_signoff[1] -or $contract.accepted_parent.default_report_sha256 -ne $sources.accepted_parent_report[1] -or $contract.accepted_parent.replication_report_sha256 -ne $sources.accepted_parent_replication_report[1] -or $contract.excluded_diagnostic.input_sha256 -ne $sources.excluded_diagnostic_input[1] -or $contract.excluded_diagnostic.closure_sha256 -ne $sources.excluded_diagnostic_closure[1] -or $contract.report_window_precedent.signoff_sha256 -ne $sources.J05_signoff[1] -or $contract.report_settings.installed_sha256 -ne $sources.default_settings[1] -or $contract.report_settings.one_byte_outpr_enabled_sha256 -ne $sources.report_settings[1] -or $contract.parameters.nreps -ne 128 -or $contract.parameters.tclev -ne 0 -or $contract.parameters.simulation_horizon_hours -ne 1032 -or $contract.parameters.control_and_mission_collection_end_hours -ne 1032 -or $contract.parameters.system_collection_window_hours[1] -ne 48) { throw 'contract fields differ' }
if ($contract.expected_converter.errors -ne 0 -or $contract.expected_converter.warnings -ne 1 -or $contract.expected_converter.notes -ne 0 -or ($contract.expected_converter.warning_codes_in_order -join ',') -ne '108') { throw 'converter contract differs' }
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
$runCreated = $false
$runSealed = $false
$fatalError = $null
try {
  Trace "F04.$Arm preflight: queue"
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide native queue busy' }
  $gui = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  Trace "F04.$Arm preflight: GUI identity"
  if ($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -le 0) { throw 'expected GUI PID 13340 only' }
  $guiSession = $gui[0].SessionId
  $guiStart = $gui[0].StartTime.ToUniversalTime().ToString('o')
  $sessions = @(qwinsta 2>&1)
  Trace "F04.$Arm preflight: GUI session"
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session not active' }
  function Assert-Gui {
    $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
    if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'GUI process changed' }
  }
  New-Item -ItemType Directory -Path $run -Force | Out-Null
  $runCreated = $true
  Trace "F04.$Arm native: run directory created"
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
  [ordered]@{ schema='simlox-f04-system-window-native/ssh-cli-v1'; run_id=$RunId; created_utc=(Get-Date).ToUniversalTime().ToString('o'); original_run_dir=$run; execution_mode='ssh_cli_v1'; session_id=0; ssh_ancestor_names=$ancestors; gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart}; queue_mutex='Global\SimloxIssue18NativeQueue'; working_directory=$workingDirectory; planned_commands=@($commands | ForEach-Object { [ordered]@{name=$_.name;arguments=$_.args} }); source_hashes_before=$sourceHashes; arm=$Arm; publication_state='not_published' } | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps = @(); $errorText = $null
  foreach ($command in $commands) {
    Trace "F04.$Arm native: $($command.name)"
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
        $warningCodes = @([regex]::Matches($log, '\(warning #(\d+)\)') | ForEach-Object { $_.Groups[1].Value })
        if ($log -notmatch 'Input conversion completed\. Errors: 0, Warnings: 1, Notes: 0' -or
            ($warningCodes -join ',') -ne '108' -or
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
  foreach ($name in @('build.py','describe_diff.py','make_report_settings.py','check_roundtrip.py','run_native_ssh.ps1')) { $sourceHashesAfter[$name] = (Get-FileHash -LiteralPath (Join-Path $case $name) -Algorithm SHA256).Hash.ToLowerInvariant() }
  $sourceHashesAfter.python = (Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant()
  foreach ($key in $sourceHashes.Keys) { if ($sourceHashes[$key] -ne $sourceHashesAfter[$key]) { $errorText = "source changed during run: $key" } }
  $raw = @{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File) { if ($file.Name -ne 'invocation.json') { $raw[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} } }
  [ordered]@{schema='simlox-f04-system-window-native-closure/v1';run_id=$RunId;invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();source_hashes_before=$sourceHashes;source_hashes_after=$sourceHashesAfter;raw=$raw;error=$errorText;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
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
      [ordered]@{schema='simlox-f04-system-window-native-closure/v1';run_id=$RunId;invocation_sha256=$invocationSha;source_hashes_before=$sourceHashes;source_hashes_after=$null;raw=$partialRaw;error=$fatalError;publication_state='excluded_diagnostic';partial=$true} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
    } catch { Write-Error "partial closure failed: $($_.Exception.Message)" }
  }
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

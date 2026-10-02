param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
  [Parameter(Mandatory=$true)][ValidateSet('position-monit-y')][string]$Arm
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$root = Split-Path $case -Parent
$inputPath = Join-Path $case 'native-input.json'
$parentY = Join-Path $root 'D14-var01-monitored-item-pm-v1.0.1\native-input-monitored.json'
$parentYClosure = Join-Path $root 'D14-var01-monitored-item-pm-v1.0.1\runs\d14-var01-monitored-v101-ssh-20261002-01\closure.json'
$parentN = Join-Path $root 'D14-var01-monitored-item-pm-v1.0.1\native-input-system-converted.json'
$parentNClosure = Join-Path $root 'D14-var01-monitored-item-pm-v1.0.1\runs\d14-var01-system-converted-v101-ssh-20261002-01\closure.json'
$contract = Join-Path $case 'contract.json'
$diff = Join-Path $case 'exact-diff.json'
$builder = Join-Path $case 'build.py'
$diffBuilder = Join-Path $case 'describe_diff.py'
$checker = Join-Path $case 'check_roundtrip.py'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary = 'C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$work = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run = Join-Path (Join-Path $case 'runs') $RunId
$inputSha = 'cda1509cdf704a92b374c3aed3b40b49ade2598189406368ad2b56e0564e5a03'
$expected = [ordered]@{
  input=$inputSha
  parent_y='29dd9638ecaf5980b7ecf90ef41644afbbcca3a9b15f88dceb8f2fe3e5c32903'
  parent_y_closure='7a0977eefefb06be79860ad0982efa2f8c0d4259c8b0905e2a17a5fca9122ead'
  parent_n='9e6f77519511e72eb732dc5c67b19a8dab16a166ca9d33a50917bb04b88ae9f9'
  parent_n_closure='acd80471d0d298731102e8c9e08d12753557b35b77453c54eb213e0e919e0b85'
  contract='ae9bfac4ef1f38532ba41d01e4786bf4313373e46966e6f0572a103103198fa9'
  exact_diff='83f09477630a0dc74b276780ecda30c852dceb6558dca122ad1687cd5e49f28c'
  exe='fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
  manual='39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3'
  dictionary='11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0'
}
$paths = @{input=$inputPath; parent_y=$parentY; parent_y_closure=$parentYClosure; parent_n=$parentN; parent_n_closure=$parentNClosure; contract=$contract; exact_diff=$diff; exe=$exe; manual=$manual; dictionary=$dictionary}
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if (Test-Path -LiteralPath $run) { throw 'immutable run ID already exists' }
$ancestors = @()
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'sshd ancestor absent' }
foreach ($key in $expected.Keys) {
  if (-not (Test-Path -LiteralPath $paths[$key]) -or (Get-FileHash -LiteralPath $paths[$key] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected[$key]) { throw "frozen fingerprint differs: $key" }
}
foreach ($path in @($contract,$builder,$diffBuilder,$checker,$python,$work)) { if (-not (Test-Path -LiteralPath $path)) { throw "missing source: $path" } }
$frozen = Get-Content -LiteralPath $contract -Raw | ConvertFrom-Json
if ($frozen.case_id -ne 'D14' -or $frozen.variant_id -ne 'D14.var04' -or $frozen.input_sha256 -ne $inputSha -or $frozen.accepted_parent.input_sha256 -ne $expected.parent_y -or $frozen.accepted_parent.native_closure_sha256 -ne $expected.parent_y_closure -or $frozen.exact_diff_sha256 -ne $expected.exact_diff) { throw 'contract pins differ' }
& $python $builder | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'builder verification failed' }
& $python $diffBuilder | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'diff verification failed' }
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$held = $false
try {
  try { $held = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $held = $true }
  if (-not $held) { throw 'native queue busy' }
  $existing = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -le 0) { throw 'GUI PID 13340 identity differs' }
  $guiStart = $existing[0].StartTime.ToUniversalTime().ToString('o')
  $guiSession = $existing[0].SessionId
  $sessions = @(qwinsta 2>&1)
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session inactive' }
  function Assert-Gui {
    $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
    if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'GUI process changed' }
  }
  $sourcePaths = [ordered]@{input=$inputPath; parent_y=$parentY; parent_y_closure=$parentYClosure; parent_n=$parentN; parent_n_closure=$parentNClosure; contract=$contract; exact_diff=$diff; builder=$builder; diff_builder=$diffBuilder; checker=$checker; runner=$PSCommandPath; python=$python; exe=$exe; manual=$manual; dictionary=$dictionary}
  function Source-Hashes { $h=[ordered]@{}; foreach ($key in $sourcePaths.Keys) { $h[$key]=(Get-FileHash -LiteralPath $sourcePaths[$key] -Algorithm SHA256).Hash.ToLowerInvariant() }; return $h }
  $before = Source-Hashes
  New-Item -ItemType Directory -Path $run -Force | Out-Null
  Copy-Item -LiteralPath $inputPath -Destination (Join-Path $run 'input.json')
  if ((Get-FileHash -LiteralPath (Join-Path $run 'input.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $inputSha) { throw 'copied input differs' }
  $source = Join-Path $run 'input.json'; $sxi = Join-Path $run 'model.sxi'; $sxo = Join-Path $run 'model.sxo'; $round = Join-Path $run 'roundtrip-raw.json'
  $commands = @(
    [pscustomobject]@{name='import'; args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $source,$sxi,(Join-Path $run 'import.log'))},
    [pscustomobject]@{name='export'; args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,$round,(Join-Path $run 'export.log'))},
    [pscustomobject]@{name='calc'; args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log'))}
  )
  [ordered]@{schema='simlox-d14-var04-position-monit-diagnostic-invocation/v1'; case_id='D14'; variant_id='D14.var04'; arm=$Arm; run_id=$RunId; created_utc=(Get-Date).ToUniversalTime().ToString('o'); original_run_dir=$run; source_hashes_before=$before; execution_mode='session0_ssh_cli'; session_id=(Get-Process -Id $PID).SessionId; ssh_ancestor_names=$ancestors; gui=[ordered]@{pid=13340; session_id=$guiSession; start_utc=$guiStart}; queue_mutex='Global\SimloxIssue18NativeQueue'; working_directory=$work; planned_commands=$commands; publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps=@(); $errorText=$null
  foreach ($command in $commands) {
    $step=[ordered]@{name=$command.name; arguments=$command.args; started_utc=(Get-Date).ToUniversalTime().ToString('o'); completed_utc=$null; exit_code=$null; gui_preserved=$false; status='started'; error=$null}
    $steps += $step
    try {
      Assert-Gui
      $process=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $work -WindowStyle Hidden -PassThru -Wait
      $step.exit_code=$process.ExitCode
      Assert-Gui; $step.gui_preserved=$true
      if ($command.name -ne 'calc' -and $step.exit_code -ne 0) { throw "$($command.name) exit=$($step.exit_code)" }
      $required=switch ($command.name) { 'import' {@('model.sxi','import.log')} 'export' {@('roundtrip-raw.json','export.log')} 'calc' {@('run.log')} }
      foreach ($name in $required) { $p=Join-Path $run $name; if (-not (Test-Path -LiteralPath $p) -or (Get-Item -LiteralPath $p).Length -le 4) { throw "$($command.name) output missing: $name" } }
      if ($command.name -eq 'calc') {
        $log=Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw
        if ($log -notmatch 'Input conversion completed\. Errors: [1-9]\d*, Warnings: \d+, Notes: \d+') { throw 'expected converter rejection marker absent' }
        if ($log -notmatch '\(error #\d+\)') { throw 'converter error diagnostic absent' }
        if ((Test-Path -LiteralPath $sxo) -and (Get-Item -LiteralPath $sxo).Length -gt 4) { throw 'invalid source produced nonempty simulation output' }
        $step.status='expected_rejection'
      } else {
        $step.status='completed'
      }
    } catch { $errorText=$_.Exception.Message; $step.status='failed'; $step.error=$errorText; break }
    finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
  }
  if (-not $errorText) {
    $step=[ordered]@{name='check_import_export'; started_utc=(Get-Date).ToUniversalTime().ToString('o'); completed_utc=$null; exit_code=$null; gui_preserved=$false; status='started'; error=$null}; $steps += $step
    try { Assert-Gui; & $python $checker $run $Arm | Set-Content -LiteralPath (Join-Path $run 'roundtrip-validation.json') -Encoding UTF8; $step.exit_code=$LASTEXITCODE; Assert-Gui; $step.gui_preserved=$true; if ($step.exit_code -ne 0) { throw 'roundtrip check failed' }; $step.status='completed' }
    catch { $errorText=$_.Exception.Message; $step.status='failed'; $step.error=$errorText }
    finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
  }
  $after=Source-Hashes
  foreach ($key in $before.Keys) { if ($before[$key] -ne $after[$key]) { $errorText="source changed during run: $key" } }
  $raw=[ordered]@{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File) { if ($file.Name -ne 'invocation.json') { $raw[$file.Name]=[ordered]@{bytes=$file.Length; sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} } }
  [ordered]@{schema='simlox-d14-var04-position-monit-diagnostic-closure/v1'; arm=$Arm; run_id=$RunId; invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant(); source_hashes_before=$before; source_hashes_after=$after; raw=$raw; error=$errorText; publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{run_id=$RunId; arm=$Arm; run_dir=$run; native_steps='completed'} | ConvertTo-Json)
} finally { if ($held) { $queue.ReleaseMutex() | Out-Null }; $queue.Dispose() }

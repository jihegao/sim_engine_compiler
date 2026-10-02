param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
  [Parameter(Mandatory=$true)][ValidateSet('ophours-only','missions-plus-ophours')][string]$Arm
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$root = Split-Path $case -Parent
$inputPath = Join-Path $case "native-input-$Arm.json"
$parentY = Join-Path $root 'D14-var03-post-reinstallation-pm-v1.0.0\native-input-monitored.json'
$parentYClosure = Join-Path $root 'D14-var03-post-reinstallation-pm-v1.0.0\runs\d14-var03-post-reinstall-monitored-v100-ssh-20261002-01\closure.json'
$parentN = Join-Path $root 'D14-var03-post-reinstallation-pm-v1.0.0\native-input-system-converted.json'
$parentNClosure = Join-Path $root 'D14-var03-post-reinstallation-pm-v1.0.0\runs\d14-var03-post-reinstall-system-converted-v100-ssh-20261002-01\closure.json'
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
$inputSha = @{'ophours-only'='4e2ef5e138628b6afe9585afe140bab5a190bc77e3d7e6de18b1e1700c1c22d9'; 'missions-plus-ophours'='12c30f7306cc62c3667f3efb86c569ebe982fbb5dbc6f34d366dd5a8d8d98d6a'}[$Arm]
$expected = [ordered]@{
  input=$inputSha
  parent_y='48a3eea3f6f9c32fd79bcc9f544845e2e60f5767987b37605563b5bf2738c9dd'
  parent_y_closure='ef5694117dc43171508ac7d49065605b67f4c9be546900f09de5d9b76a245276'
  parent_n='e93643ecc8765a1a132b8c71445729fceff44b034059a4f2a2274879c1b47a37'
  parent_n_closure='f59ac3c986fd37e532ccf25cd055c395103a14fd49d30b187c2deeb299c1008f'
  contract='56747857997d5ca04cb5668f6e7c4008a852b95689e388917ba0d678ed5b79e9'
  exact_diff='d7b39c9b1c1b985efc48dd559c9d3e7347740a9e71f59369070ba2e6f861baeb'
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
if ($frozen.case_id -ne 'D14' -or $frozen.variant_id -ne 'D14.var05' -or $frozen.inputs.$Arm.sha256 -ne $inputSha -or $frozen.accepted_parent.input_sha256 -ne $expected.parent_y -or $frozen.accepted_parent.native_closure_sha256 -ne $expected.parent_y_closure -or $frozen.exact_diff_sha256 -ne $expected.exact_diff) { throw 'contract pins differ' }
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
  $source = Join-Path $run 'input.json'; $sxi = Join-Path $run 'model.sxi'; $sxo = Join-Path $run 'model.sxo'; $round = Join-Path $run 'roundtrip-raw.json'; $report = Join-Path $run 'report-raw.json'
  $commands = @(
    [pscustomobject]@{name='import'; args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $source,$sxi,(Join-Path $run 'import.log'))},
    [pscustomobject]@{name='export'; args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,$round,(Join-Path $run 'export.log'))},
    [pscustomobject]@{name='calc'; args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log'))},
    [pscustomobject]@{name='jsonreport'; args=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,$report,(Join-Path $run 'report-export.log'))}
  )
  [ordered]@{schema='simlox-d14-var05-multi-counter-ssh-invocation/v1'; case_id='D14'; variant_id='D14.var05'; arm=$Arm; run_id=$RunId; created_utc=(Get-Date).ToUniversalTime().ToString('o'); original_run_dir=$run; source_hashes_before=$before; execution_mode='session0_ssh_cli'; session_id=(Get-Process -Id $PID).SessionId; ssh_ancestor_names=$ancestors; gui=[ordered]@{pid=13340; session_id=$guiSession; start_utc=$guiStart}; queue_mutex='Global\SimloxIssue18NativeQueue'; working_directory=$work; planned_commands=$commands; publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps=@(); $errorText=$null
  foreach ($command in $commands) {
    $step=[ordered]@{name=$command.name; arguments=$command.args; started_utc=(Get-Date).ToUniversalTime().ToString('o'); completed_utc=$null; exit_code=$null; gui_preserved=$false; status='started'; error=$null}
    $steps += $step
    try {
      Assert-Gui
      $process=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $work -WindowStyle Hidden -PassThru -Wait
      $step.exit_code=$process.ExitCode
      Assert-Gui; $step.gui_preserved=$true
      if ($step.exit_code -ne 0) { throw "$($command.name) exit=$($step.exit_code)" }
      $required=switch ($command.name) { 'import' {@('model.sxi','import.log')} 'export' {@('roundtrip-raw.json','export.log')} 'calc' {@('model.sxo','model.log','run.log')} 'jsonreport' {@('report-raw.json','report-export.log')} }
      foreach ($name in $required) { $p=Join-Path $run $name; if (-not (Test-Path -LiteralPath $p) -or (Get-Item -LiteralPath $p).Length -le 4) { throw "$($command.name) output missing: $name" } }
      if ($command.name -eq 'calc') {
        $log=Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw
        if ($log -notmatch 'Input conversion completed\. Errors: 0, Warnings: (\d+), Notes: 0') { throw 'conversion errors or marker absent' }
        $conversionText=($log -split 'Input conversion completed\. Errors: 0, Warnings: \d+, Notes: 0',2)[0]
        $runtimeText=($log -split 'Input conversion completed\. Errors: 0, Warnings: \d+, Notes: 0',2)[1]
        $warn=@([regex]::Matches($conversionText,'\(warning #(\d+)\)') | ForEach-Object { $_.Groups[1].Value })
        if ($warn.Count -ne [int]$Matches[1] -or @($warn | Where-Object { $_ -notin @('108','126') }).Count -gt 0) { throw 'unexpected warnings' }
        if ([regex]::IsMatch($runtimeText,'\(warning #\d+\)|\(error #\d+\)')) { throw 'runtime warnings or errors require case review' }
      }
      $step.status='completed'
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
  [ordered]@{schema='simlox-d14-var05-multi-counter-ssh-closure/v1'; arm=$Arm; run_id=$RunId; invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant(); source_hashes_before=$before; source_hashes_after=$after; raw=$raw; error=$errorText; publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{run_id=$RunId; arm=$Arm; run_dir=$run; native_steps='completed'} | ConvertTo-Json)
} finally { if ($held) { $queue.ReleaseMutex() | Out-Null }; $queue.Dispose() }

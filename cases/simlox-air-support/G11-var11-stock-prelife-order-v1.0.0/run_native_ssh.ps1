param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
  [Parameter(Mandatory=$true)][ValidateSet('age10-first','age70-first')][string]$Arm
)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$root=Split-Path $case -Parent
$inputPath=Join-Path $case "native-input-$Arm.json"
$parent=Join-Path $root 'G11-var04-inherit-item-prelife-v1.0.1\native-input-explicit-control.json'
$parentClosure=Join-Path $root 'G11-var04-inherit-item-prelife-v1.0.1\runs\g11-var04-explicit-control-v101-ssh-20261002-01\closure.json'
$contract=Join-Path $case 'contract.json'; $diff=Join-Path $case 'exact-diff.json'
$builder=Join-Path $case 'build.py'; $diffBuilder=Join-Path $case 'describe_diff.py'; $checker=Join-Path $case 'check_roundtrip.py'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary='C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run=Join-Path (Join-Path $case 'runs') $RunId
$inputSha=@{'age10-first'='c7a32b5247076b31c9b5887113220902384076e597fefda306d1798b524f048a'; 'age70-first'='e98d18cffaa7cf177595de7e0899766d586cd43720b684fea884ca93d2e1372c'}[$Arm]
$expected=[ordered]@{
  input=$inputSha
  parent='76cd71fe989b84a8f8c5c23007926a417c8f01c820cfc534846216e4a9fe7311'
  parent_closure='60ae9d2e2feadb6843cec3d1bb53c7afa7b59fc9374d5a35018df1aa1a2cb4f7'
  contract='6191891eb422b417caea43a87cd6bf6c26037f8c0526c0600c3a3e34b50d60ad'
  exact_diff='b5320f54915edcd258c6319df0464c32e1576a449872ef4832a5628d38a6f73b'
  exe='fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
  manual='39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3'
  dictionary='11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0'
}
$paths=@{input=$inputPath;parent=$parent;parent_closure=$parentClosure;contract=$contract;exact_diff=$diff;exe=$exe;manual=$manual;dictionary=$dictionary}
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if (Test-Path -LiteralPath $run) { throw 'immutable run ID already exists' }
$ancestors=@(); $ancestorPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) { $a=Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"; if (-not $a) { break }; $ancestors+=$a.Name; $ancestorPid=$a.ParentProcessId }
if ($ancestors -notcontains 'sshd.exe') { throw 'sshd ancestor absent' }
foreach($key in $expected.Keys) { if (-not (Test-Path -LiteralPath $paths[$key]) -or (Get-FileHash -LiteralPath $paths[$key] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected[$key]) { throw "frozen fingerprint differs: $key" } }
foreach($p in @($contract,$builder,$diffBuilder,$checker,$python,$work)) { if (-not (Test-Path -LiteralPath $p)) { throw "missing source: $p" } }
$frozen=Get-Content -LiteralPath $contract -Raw | ConvertFrom-Json
if ($frozen.case_id -ne 'G11' -or $frozen.variant_id -ne 'G11.var11' -or $frozen.inputs.$Arm.sha256 -ne $inputSha -or $frozen.accepted_parent.input_sha256 -ne $expected.parent -or $frozen.accepted_parent.native_closure_sha256 -ne $expected.parent_closure -or $frozen.exact_diff_sha256 -ne $expected.exact_diff) { throw 'contract pins differ' }
& $python $builder | Out-Null; if ($LASTEXITCODE -ne 0) { throw 'builder verification failed' }
& $python $diffBuilder | Out-Null; if ($LASTEXITCODE -ne 0) { throw 'diff verification failed' }
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue'); $held=$false
try {
  try { $held=$queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $held=$true }
  if (-not $held) { throw 'native queue busy' }
  $gui=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -le 0 -or $gui[0].StartTime.ToUniversalTime().ToString('o') -ne '2026-09-28T10:09:56.8261381Z') { throw 'GUI identity differs' }
  $guiStart=$gui[0].StartTime.ToUniversalTime().ToString('o'); $guiSession=$gui[0].SessionId
  $sessions=@(qwinsta 2>&1)
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session inactive' }
  $optionKey='HKCU:\Software\Systecon\SIMLOX Version 2017\Prelife Settings'
  $optionOriginal=(Get-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog).UsePrelifeLog
  if ($optionOriginal -ne 'NO') { throw "Prelife Log option expected NO, got $optionOriginal" }
  function Assert-Gui { $p=@(Get-Process Simlox -ErrorAction SilentlyContinue); if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'GUI changed' } }
  $sourcePaths=[ordered]@{input=$inputPath;parent=$parent;parent_closure=$parentClosure;contract=$contract;exact_diff=$diff;builder=$builder;diff_builder=$diffBuilder;checker=$checker;runner=$PSCommandPath;python=$python;exe=$exe;manual=$manual;dictionary=$dictionary}
  function Source-Hashes { $h=[ordered]@{}; foreach($key in $sourcePaths.Keys) { $h[$key]=(Get-FileHash -LiteralPath $sourcePaths[$key] -Algorithm SHA256).Hash.ToLowerInvariant() }; return $h }
  $before=Source-Hashes
  New-Item -ItemType Directory -Path $run -Force | Out-Null
  Copy-Item -LiteralPath $inputPath -Destination (Join-Path $run 'input.json')
  if ((Get-FileHash -LiteralPath (Join-Path $run 'input.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $inputSha) { throw 'copied input differs' }
  $source=Join-Path $run 'input.json'; $sxi=Join-Path $run 'model.sxi'; $sxo=Join-Path $run 'model.sxo'; $round=Join-Path $run 'roundtrip-raw.json'; $report=Join-Path $run 'report-raw.json'
  $commands=@(
    [pscustomobject]@{name='import';args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $source,$sxi,(Join-Path $run 'import.log'))},
    [pscustomobject]@{name='export';args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,$round,(Join-Path $run 'export.log'))},
    [pscustomobject]@{name='calc';args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log'))},
    [pscustomobject]@{name='jsonreport';args=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,$report,(Join-Path $run 'report-export.log'))}
  )
  [ordered]@{schema='simlox-g11-var11-ssh-invocation/v1';case_id='G11';variant_id='G11.var11';arm=$Arm;run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');original_run_dir=$run;source_hashes_before=$before;execution_mode='session0_ssh_cli';session_id=(Get-Process -Id $PID).SessionId;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';prelife_log_option_before=$optionOriginal;working_directory=$work;planned_commands=$commands;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps=@(); $errorText=$null
  foreach($command in $commands) {
    $step=[ordered]@{name=$command.name;arguments=$command.args;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;gui_preserved=$false;status='started';error=$null}; $steps+=$step
    try {
      Assert-Gui
      if ($command.name -eq 'calc') {
        try {
          Set-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog -Value 'YES'
          $process=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $work -WindowStyle Hidden -PassThru -Wait
        } finally { Set-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog -Value $optionOriginal }
      } else { $process=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $work -WindowStyle Hidden -PassThru -Wait }
      $step.exit_code=$process.ExitCode
      Assert-Gui; $step.gui_preserved=$true
      if ((Get-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog).UsePrelifeLog -ne $optionOriginal) { throw 'Prelife Log option not restored' }
      if ($step.exit_code -ne 0) { throw "$($command.name) exit=$($step.exit_code)" }
      $required=switch($command.name) { 'import' {@('model.sxi','import.log')} 'export' {@('roundtrip-raw.json','export.log')} 'calc' {@('model.sxo','model.log','model_Prelife.log','run.log')} 'jsonreport' {@('report-raw.json','report-export.log')} }
      foreach($name in $required) { $p=Join-Path $run $name; if (-not (Test-Path -LiteralPath $p) -or (Get-Item -LiteralPath $p).Length -le 4) { throw "$($command.name) output missing: $name" } }
      if ($command.name -eq 'calc') {
        $log=Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw
        if ($log -notmatch 'Input conversion completed\. Errors: 0, Warnings: (\d+), Notes: 0') { throw 'conversion errors or marker absent' }
        $conversionText=($log -split 'Input conversion completed\. Errors: 0, Warnings: \d+, Notes: 0',2)[0]
        $runtimeText=($log -split 'Input conversion completed\. Errors: 0, Warnings: \d+, Notes: 0',2)[1]
        $warningCount=[int]$Matches[1]
        $warnings=@(); $form=''
        foreach($line in ($conversionText -split "`r?`n")) {
          if ($line -match '^Form: (.+)$') { $form=$Matches[1] }
          if ($line -match '\(warning #(\d+)\)') {
            $code=$Matches[1]
            $classification=if ($code -eq '108') { 'event-log-enabled' }
              elseif ($form -eq 'PrelifeData' -and ($line -match '(?i)inherit' -or ($line -match '(?i)age' -and $line -match '(?i)ignor'))) { 'inherit-ignores-age' }
              else { 'unreviewed' }
            $warnings+=@([ordered]@{form=$form;code=$code;line=$line;classification=$classification})
          }
        }
        $expectedCodes=@('108')
        if ($warnings.Count -ne $warningCount -or @($warnings | Where-Object { $_.classification -eq 'unreviewed' }).Count -gt 0 -or (($warnings | ForEach-Object { $_.code }) -join ',') -ne ($expectedCodes -join ',')) { throw 'unexpected warnings' }
        if ([regex]::IsMatch($runtimeText,'\(warning #\d+\)|\(error #\d+\)')) { throw 'runtime warnings or errors require review' }
      }
      $step.status='completed'
    } catch { $errorText=$_.Exception.Message; $step.status='failed'; $step.error=$errorText; break }
    finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
  }
  if (-not $errorText) {
    $step=[ordered]@{name='check_import_export';started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;gui_preserved=$false;status='started';error=$null}; $steps+=$step
    try { Assert-Gui; & $python $checker $run $Arm | Set-Content -LiteralPath (Join-Path $run 'roundtrip-validation.json') -Encoding UTF8; $step.exit_code=$LASTEXITCODE; Assert-Gui; $step.gui_preserved=$true; if ($step.exit_code -ne 0) { throw 'roundtrip check failed' }; $step.status='completed' }
    catch { $errorText=$_.Exception.Message; $step.status='failed'; $step.error=$errorText }
    finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
  }
  $after=Source-Hashes; foreach($key in $before.Keys) { if ($before[$key] -ne $after[$key]) { $errorText="source changed during run: $key" } }
  if ((Get-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog).UsePrelifeLog -ne $optionOriginal) { $errorText='Prelife Log option not restored' }
  $raw=[ordered]@{}; foreach($file in Get-ChildItem -LiteralPath $run -File) { if ($file.Name -ne 'invocation.json') { $raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} } }
  [ordered]@{schema='simlox-g11-var11-ssh-closure/v1';arm=$Arm;run_id=$RunId;invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();source_hashes_before=$before;source_hashes_after=$after;raw=$raw;prelife_log_option_after=(Get-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog).UsePrelifeLog;error=$errorText;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{run_id=$RunId;arm=$Arm;run_dir=$run;native_steps='completed'} | ConvertTo-Json)
} finally { if ($held) { $queue.ReleaseMutex() | Out-Null }; $queue.Dispose() }

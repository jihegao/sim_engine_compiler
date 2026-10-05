param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$root=Split-Path $case -Parent
$diagnostic=Join-Path $root 'E15-var08-equal-point-v1.0.0'
$oldRun=Join-Path (Join-Path $diagnostic 'runs') 'e15-var08-equal-point-v100-ssh-20261005-01'
$selectorParent=Join-Path $root 'E15-var07-explicit-istoh-v1.0.1'
$selector=Join-Path (Join-Path $selectorParent 'runs') 'report-settings\item-position-results.sxs'
$selectorBuilder=Join-Path $selectorParent 'make_report_settings.py'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run=Join-Path (Join-Path $case 'runs') $RunId
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'a4977d8b4f52f3f27a39a5f0f52f3cce5ecf63c6f03ba7e9bc74f47c75ecb6d3')
  diagnostic_index=@((Join-Path $diagnostic 'evidence-index.json'),'4daff3fb7392dc1e61fc7cc4c9b2e618089a48076792b1fe8b3f8a7c64e86270')
  diagnostic_closure=@((Join-Path $oldRun 'closure.json'),'d097d5fb70d4376b1eb15fcf1ee6f222a254a96f9f9e1cbef8af04264efc3798')
  diagnostic_sxo=@((Join-Path $oldRun 'model.sxo'),'d8d434bc091cd72dc0b02ee93649542c6719435a47dcf8a5f230251b7b65fa4d')
  diagnostic_event=@((Join-Path $oldRun 'model.log'),'2333331c9f389f61da3a36cc5ec8bf1394d125777329a5106780f7e1ed79d34a')
  selector=@($selector,'841a6a077741566cac02b84e0cb35f4154f13a857e5665909a483cd6c051316c')
  selector_builder=@($selectorBuilder,'d2ede31eba96985da2e6671ef0f81fe0d010f5e2d6889f09531519e11c73df1e')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual=@($manual,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
}
function Assert-Gui {
  $p=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne 1 -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne '2026-09-28T10:09:56.8261381Z'){throw 'protected GUI changed'}
}
function Assert-Child([int]$childPid,[string]$needle){
  $w=Get-CimInstance Win32_Process -Filter "ProcessId=$childPid";$p=Get-Process -Id $childPid -ErrorAction Stop
  if(-not $w -or $w.Name -ne 'Simlox.exe' -or $p.SessionId -ne 0 -or -not $w.CommandLine.Contains($needle)){throw 'native child identity differs'}
}
function Assert-DiagnosticRaw {
  $old=Get-Content -LiteralPath $sources.diagnostic_closure[0] -Raw -Encoding UTF8 | ConvertFrom-Json
  if($old.error -ne 'frozen equal-point event gate failed' -or @($old.raw.PSObject.Properties).Count -ne 11 -or $old.raw.'model.sxo'.sha256 -ne $sources.diagnostic_sxo[1] -or $old.raw.'model.log'.sha256 -ne $sources.diagnostic_event[1]){throw 'excluded diagnostic lineage differs'}
  foreach($property in $old.raw.PSObject.Properties){
    $path=Join-Path $oldRun $property.Name
    if(-not(Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne [int64]$property.Value.bytes -or (Hash $path) -ne $property.Value.sha256){throw "original diagnostic raw seal differs: $($property.Name)"}
  }
}
if(-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME){throw 'session-0 SSH required'}
if($RunId -ne 'e15-var08-report-only-v101-ssh-20261005-01'){throw 'run ID differs from contract'}
if(Test-Path -LiteralPath $run){throw 'immutable report run directory occupied'}
if(-not(Test-Path -LiteralPath $work) -or -not(Test-Path -LiteralPath $python)){throw 'pinned runtime path absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$a=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $a){break};$ancestors += $a.Name;$parentPid=$a.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'sshd ancestor required'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
& $python $selectorBuilder | Out-Null
if($LASTEXITCODE -ne 0){throw 'pinned report selector verification failed'}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'E15' -or $contract.variant_id -ne 'E15.var08' -or $contract.version -ne '1.0.1-candidate' -or $contract.run_id -ne $RunId -or $contract.diagnostic_parent.evidence_index_sha256 -ne $sources.diagnostic_index[1] -or $contract.diagnostic_parent.closure_sha256 -ne $sources.diagnostic_closure[1] -or $contract.diagnostic_parent.sxo_sha256 -ne $sources.diagnostic_sxo[1] -or $contract.diagnostic_parent.event_log_sha256 -ne $sources.diagnostic_event[1] -or $contract.report_selector.settings_sha256 -ne $sources.selector[1]){throw 'frozen report contract differs'}
Assert-DiagnosticRaw
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false;$runCreated=$false;$sealed=$false;$fatal=$null
try {
  try{$acquired=$queue.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
  if(-not $acquired){throw 'host-wide native queue busy'}
  Assert-Gui
  $sessions=@(qwinsta 2>&1)
  if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {$_ -match '^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+1\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)'}).Count -ne 1){throw 'GUI session not active'}
  New-Item -ItemType Directory -Path $run -ErrorAction Stop | Out-Null;$runCreated=$true
  $before=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$before[$entry.Key]=$entry.Value[1]};$before.runner=Hash $PSCommandPath;$before.python=Hash $python
  $report=Join-Path $run 'selected-report-raw.json';$log=Join-Path $run 'report-export.log'
  $argsText=('"{0}" -silent -report -rpts "{1}" -rjexport "{2}" -log "{3}" -close' -f $sources.diagnostic_sxo[0],$selector,$report,$log)
  [ordered]@{schema='simlox-e15-var08-v101-report-invocation/ssh-cli-v1';run_id=$RunId;diagnostic_run_id=$contract.diagnostic_parent.run_id;diagnostic_closure_sha256=$sources.diagnostic_closure[1];created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=1;start_utc='2026-09-28T10:09:56.8261381Z'};queue_mutex='Global\SimloxIssue18NativeQueue';arguments=$argsText;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $step=[ordered]@{name='report_only';arguments=$argsText;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;status='started';gui_preserved=$false;error=$null};$errorText=$null;$child=$null
  try {
    Assert-Gui
    $child=Start-Process -FilePath $exe -ArgumentList $argsText -WorkingDirectory $work -WindowStyle Hidden -PassThru
    if(-not $child.WaitForExit(60000)){Assert-Child $child.Id $log;Stop-Process -Id $child.Id -Force -ErrorAction Stop;$null=$child.WaitForExit(10000);throw 'report-only watchdog timeout after 60 seconds'}
    $step.exit_code=$child.ExitCode;Assert-Gui;$step.gui_preserved=$true
    if($child.ExitCode -ne 0){throw "report-only exit=$($child.ExitCode)"}
    if(-not(Test-Path -LiteralPath $report) -or (Get-Item -LiteralPath $report).Length -le 1000){throw 'selected report absent or too small'}
    $doc=Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json
    if(-not $doc.report -or @($doc.report.tables).Count -ne 10){throw 'selected report invalid or incomplete'}
    $step.status='completed'
  } catch {$errorText=$_.Exception.Message;$step.status='failed';$step.error=$errorText}
  finally {
    if($child){$child.Refresh();if(-not $child.HasExited){try{Assert-Child $child.Id $log;Stop-Process -Id $child.Id -Force -ErrorAction Stop}catch{$errorText="targeted child cleanup failed: $($_.Exception.Message)"}}}
    $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o')
    ConvertTo-Json -InputObject @($step) -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
  }
  $after=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$after[$entry.Key]=Hash $entry.Value[0]};$after.runner=Hash $PSCommandPath;$after.python=Hash $python
  foreach($key in $before.Keys){if($before[$key] -ne $after[$key]){$errorText="source changed during report: $key"}}
  try{Assert-DiagnosticRaw}catch{$errorText=$_.Exception.Message}
  [ordered]@{status=$step.status;error=$errorText;exit_code=$step.exit_code} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-e15-var08-v101-report-closure/v1';run_id=$RunId;diagnostic_run_id=$contract.diagnostic_parent.run_id;diagnostic_closure_sha256=$sources.diagnostic_closure[1];invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;error=$errorText;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true;if($errorText){throw $errorText}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;step='report_only';status='completed'} | ConvertTo-Json)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-e15-var08-v101-report-closure/v1';run_id=$RunId;raw=$raw;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

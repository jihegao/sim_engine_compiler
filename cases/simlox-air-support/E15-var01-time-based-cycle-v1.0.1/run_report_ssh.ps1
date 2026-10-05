param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$root=Split-Path $case -Parent
$diagnostic=Join-Path $root 'E15-var01-time-based-cycle-v1.0.0'
$oldRun=Join-Path (Join-Path $diagnostic 'runs') 'e15-var01-timecycle-v100-ssh-20261005-01'
$e15=Join-Path $root 'E15-var07-explicit-istoh-v1.0.1'
$acceptedRun=Join-Path (Join-Path $e15 'runs') 'e15-var07-default-v101-ssh-20261002-01'
$acceptedItemRun=Join-Path (Join-Path $e15 'runs') 'e15-var07-default-item-v101-ssh-20261002-01'
$settingsBuilder=Join-Path $e15 'make_report_settings.py'
$settings=Join-Path (Join-Path $e15 'runs') 'report-settings\item-position-results.sxs'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run=Join-Path (Join-Path $case 'runs') $RunId
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'d42307744dc8aa8bfcadbb3e0da68149a4b7dcfc5ff93e44189f7b06f1a61857')
  diagnostic_index=@((Join-Path $diagnostic 'evidence-index.json'),'b2909eb8aaae256b6222cc98d2d2ef48b651062926b7a0cfcfdb77263d5c8e10')
  diagnostic_contract=@((Join-Path $diagnostic 'contract.json'),'e5ba51841c45e9ca099d1f063e6c6b48234af01638121bd18b538a8fe9e81965')
  diagnostic_closure=@((Join-Path $oldRun 'closure.json'),'8995ff25d54646fafa3647736f8f12850f12fee4cae6bcb52005f2dd21216a85')
  diagnostic_sxo=@((Join-Path $oldRun 'model.sxo'),'7669c9d956360dce2d9f777cb57b61fd4fb996b688e32831027502fda23863dc')
  diagnostic_event=@((Join-Path $oldRun 'model.log'),'d37165d77f783427b0311c983c3a47f32d3bc7cfc75518063036c03d6c436349')
  diagnostic_calc=@((Join-Path $oldRun 'run.log'),'99b10cebbbd90dc6567ae963b6ca394229348b6418010f87b4498fd6bb8d4c36')
  accepted_input=@((Join-Path $e15 'native-input-default.json'),'602dedfdb3491ab430abe4c68426c28203738fe1b2b1173d5d66955d00b6102e')
  accepted_sxo=@((Join-Path $acceptedRun 'model.sxo'),'d3e67fbcb619f85f0587dc021d0957a4b7a237cefc99571ace31910cd42beed3')
  accepted_event=@((Join-Path $acceptedRun 'model.log'),'f7fb876b752fd8b824defa81bd014fd05a75921d12c352a6940e51b4730bffbf')
  accepted_report=@((Join-Path $acceptedItemRun 'item-report-raw.json'),'d7ed894a40efefc577b0520a4bfb0387d9cb0ea907357eef2e058d1438d96499')
  settings_builder=@($settingsBuilder,'d2ede31eba96985da2e6671ef0f81fe0d010f5e2d6889f09531519e11c73df1e')
  settings=@($settings,'841a6a077741566cac02b84e0cb35f4154f13a857e5665909a483cd6c051316c')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual=@($manual,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
}
if(-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME){throw 'session-0 SSH required'}
if($RunId -ne 'e15-var01-timecycle-report-v101-ssh-20261005-01'){throw 'report run ID differs from contract'}
if(Test-Path -LiteralPath $run){throw 'immutable report run path occupied'}
if(-not(Test-Path -LiteralPath $work) -or -not(Test-Path -LiteralPath $python)){throw 'pinned runtime path absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$a=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $a){break};$ancestors += $a.Name;$parentPid=$a.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'sshd ancestor required'}
if(-not(Test-Path -LiteralPath $settings) -or (Hash $settings) -ne $sources.settings[1]){throw 'existing accepted report selector absent or changed'}
& $python $settingsBuilder | Out-Null
if($LASTEXITCODE -ne 0){throw 'pinned report selector verification failed'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'E15' -or $contract.variant_id -ne 'E15.var01' -or $contract.version -ne '1.0.1-candidate' -or $contract.run_id -ne $RunId -or $contract.diagnostic_parent.closure_sha256 -ne $sources.diagnostic_closure[1] -or $contract.diagnostic_parent.sxo_sha256 -ne $sources.diagnostic_sxo[1] -or $contract.accepted_parent.selected_report_sha256 -ne $sources.accepted_report[1] -or $contract.report_selector.settings_sha256 -ne $sources.settings[1]){throw 'frozen report contract differs'}
$old=Get-Content -LiteralPath $sources.diagnostic_closure[0] -Raw -Encoding UTF8 | ConvertFrom-Json
function Assert-OldRaw {
  if(@($old.raw.PSObject.Properties).Count -ne 11){throw 'original diagnostic raw inventory differs'}
  foreach($property in $old.raw.PSObject.Properties){$path=Join-Path $oldRun $property.Name;if(-not(Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne [int64]$property.Value.bytes -or (Hash $path) -ne $property.Value.sha256){throw "original raw seal differs: $($property.Name)"}}
}
Assert-OldRaw
$oldOutcome=Get-Content -LiteralPath (Join-Path $oldRun 'outcome.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$oldCalc=Get-Content -LiteralPath $sources.diagnostic_calc[0] -Raw -Encoding UTF8
if($old.run_id -ne $contract.diagnostic_parent.run_id -or $old.error -ne 'unreviewed converter diagnostic' -or $old.raw.'model.sxo'.sha256 -ne $sources.diagnostic_sxo[1] -or $old.raw.'model.log'.sha256 -ne $sources.diagnostic_event[1] -or $oldOutcome.converter_summary[0] -ne 0 -or $oldOutcome.converter_summary[1] -ne 2 -or $oldOutcome.converter_summary[2] -ne 0 -or $oldOutcome.warning_codes[0] -ne '108' -or $oldOutcome.warning_codes[1] -ne '376' -or -not $oldCalc.Contains('Form: StockAllocation'+[Environment]::NewLine+'rec 2: (warning #376) ROSIZ not used at location with time-based reorder strategy: TEACH-DU-01 / DEPOT-01')){throw 'excluded diagnostic lineage differs'}
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false;$runCreated=$false;$sealed=$false;$fatal=$null
try {
  try{$acquired=$queue.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
  if(-not $acquired){throw 'host-wide native queue busy'}
  $gui=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -ne 1 -or $gui[0].StartTime.ToUniversalTime().ToString('o') -ne '2026-09-28T10:09:56.8261381Z'){throw 'protected GUI identity differs'}
  $script:guiStart=$gui[0].StartTime.ToUniversalTime().ToString('o')
  $sessions=@(qwinsta 2>&1)
  if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {$_ -match '^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+1\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)'}).Count -ne 1){throw 'GUI session not active'}
  function Assert-Gui {$p=@(Get-Process Simlox -ErrorAction SilentlyContinue);if($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne 1 -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $script:guiStart){throw 'protected GUI changed'}}
  function Assert-Child([int]$childPid,[string]$needle){$w=Get-CimInstance Win32_Process -Filter "ProcessId=$childPid";$p=Get-Process -Id $childPid -ErrorAction Stop;if(-not $w -or $w.Name -ne 'Simlox.exe' -or $p.SessionId -ne 0 -or -not $w.CommandLine.Contains($needle)){throw 'native child identity differs'}}
  New-Item -ItemType Directory -Path $run -ErrorAction Stop | Out-Null;$runCreated=$true
  $before=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$before[$entry.Key]=$entry.Value[1]};$before.runner=Hash $PSCommandPath;$before.python=Hash $python
  $report=Join-Path $run 'selected-report-raw.json';$log=Join-Path $run 'report-export.log'
  $argsText=('"{0}" -silent -report -rpts "{1}" -rjexport "{2}" -log "{3}" -close' -f $sources.diagnostic_sxo[0],$settings,$report,$log)
  [ordered]@{schema='simlox-e15-var01-timecycle-report-invocation/ssh-cli-v1';run_id=$RunId;parent_run_id=$old.run_id;parent_closure_sha256=$sources.diagnostic_closure[1];created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=1;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';arguments=$argsText;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $step=[ordered]@{name='selected_report_only';arguments=$argsText;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;status='started';gui_preserved=$false;error=$null}
  $errorText=$null;$child=$null
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
  try{Assert-OldRaw}catch{$errorText=$_.Exception.Message}
  [ordered]@{status=$step.status;error=$errorText;exit_code=$step.exit_code} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-e15-var01-timecycle-report-closure/v1';run_id=$RunId;parent_run_id=$old.run_id;parent_closure_sha256=$sources.diagnostic_closure[1];invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;error=$errorText;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true;if($errorText){throw $errorText}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;step='selected_report_only';status='completed'} | ConvertTo-Json)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-e15-var01-timecycle-report-closure/v1';run_id=$RunId;raw=$raw;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

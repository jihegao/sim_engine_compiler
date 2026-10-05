param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$root=Split-Path $case -Parent
$parent=Join-Path $root 'I07-var10-nonreorder-base-v1.0.0'
$parentRun=Join-Path (Join-Path $parent 'runs') 'i07-var10-nonreorder-base-v100-ssh-20261005-01'
$e15=Join-Path $root 'E15-var07-explicit-istoh-v1.0.1'
$settingsBuilder=Join-Path $e15 'make_report_settings.py'
$settings=Join-Path (Join-Path $e15 'runs') 'report-settings\item-position-results.sxs'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run=Join-Path (Join-Path $case 'runs') $RunId
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'8b5bf5cc6938e6f2e4d8e57aa3dc45bf0e1dbc6598b032da7b8a85709245074c')
  diagnostic_index=@((Join-Path $parent 'evidence-index.json'),'cffc5ceace86d89da7ea5ffc33d5e287fd0eefbea1e27cea391d209713937542')
  diagnostic_contract=@((Join-Path $parent 'contract.json'),'0d9b2857583c5d1aadf8ee75d407f62433bf79662d1c8c65dd62caf1c49370c3')
  diagnostic_closure=@((Join-Path $parentRun 'closure.json'),'4e54e45660e4a7fe4f2793ab622d75f9b2aa5f0c1830b16ec036e0a78fe8572d')
  child_sxo=@((Join-Path $parentRun 'change.sxo'),'37cd82fdf1f60d0f6055f3f57f0254c4231d3bc1b18e514c3f034df6fde8571f')
  control_sxo=@((Join-Path $parentRun 'control.sxo'),'08aba19408d1bbd1fa9a29fc2b8810f3549c2c50985e0170a50469801474bd91')
  control_report=@((Join-Path $parentRun 'control-report-raw.json'),'e56a2de326bf91f50d6155f5a81ed5f881fa352e2aebb62e804564dbb3536405')
  control_log=@((Join-Path $parentRun 'control.log'),'06629a8dc4688786012a304b0e0d6b390a684349b6a280c00b3a6555e3ba5960')
  child_log=@((Join-Path $parentRun 'change.log'),'06629a8dc4688786012a304b0e0d6b390a684349b6a280c00b3a6555e3ba5960')
  settings_builder=@($settingsBuilder,'d2ede31eba96985da2e6671ef0f81fe0d010f5e2d6889f09531519e11c73df1e')
  settings=@($settings,'841a6a077741566cac02b84e0cb35f4154f13a857e5665909a483cd6c051316c')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual=@($manual,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
}
if(-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME){throw 'session-0 SSH required'}
if($RunId -ne 'i07-var10-report-only-v101-ssh-20261005-01'){throw 'report run ID differs from contract'}
if(Test-Path -LiteralPath $run){throw 'immutable report run path already exists'}
if(-not(Test-Path -LiteralPath $work) -or -not(Test-Path -LiteralPath $python)){throw 'pinned runtime path absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$a=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $a){break};$ancestors += $a.Name;$parentPid=$a.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'sshd ancestor required'}
if(-not(Test-Path -LiteralPath $settings) -or (Hash $settings) -ne $sources.settings[1]){throw 'existing accepted report selector absent or changed'}
& $python $settingsBuilder | Out-Null
if($LASTEXITCODE -ne 0){throw 'pinned report selector verification failed'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'I07' -or $contract.variant_id -ne 'I07.var10' -or $contract.version -ne '1.0.1-candidate' -or $contract.run_id -ne $RunId -or $contract.diagnostic_parent.closure_sha256 -ne $sources.diagnostic_closure[1] -or $contract.diagnostic_parent.child_sxo_sha256 -ne $sources.child_sxo[1] -or $contract.diagnostic_parent.control_report_sha256 -ne $sources.control_report[1] -or $contract.report_selector.settings_sha256 -ne $sources.settings[1]){throw 'frozen report contract differs'}
$old=Get-Content -LiteralPath $sources.diagnostic_closure[0] -Raw -Encoding UTF8 | ConvertFrom-Json
function Assert-ParentRaw {
  if(@($old.raw.PSObject.Properties).Count -ne 22){throw 'original diagnostic raw inventory differs'}
  foreach($property in $old.raw.PSObject.Properties){
    $path=Join-Path $parentRun $property.Name
    if(-not(Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -ne [int64]$property.Value.bytes -or (Hash $path) -ne $property.Value.sha256){throw "original diagnostic raw seal differs: $($property.Name)"}
  }
}
Assert-ParentRaw
$oldOutcome=Get-Content -LiteralPath (Join-Path $parentRun 'outcome.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$childRunLog=Get-Content -LiteralPath (Join-Path $parentRun 'change-run.log') -Raw -Encoding UTF8
if($old.run_id -ne $contract.diagnostic_parent.run_id -or $old.error -ne 'change unreviewed converter diagnostic' -or $old.raw.'change.sxo'.sha256 -ne $sources.child_sxo[1] -or $old.raw.'control-report-raw.json'.sha256 -ne $sources.control_report[1] -or $old.raw.'change.log'.sha256 -ne $sources.child_log[1] -or $old.raw.'control.log'.sha256 -ne $sources.control_log[1] -or $oldOutcome.converter_summaries.change[0] -ne 0 -or $oldOutcome.converter_summaries.change[1] -ne 2 -or $oldOutcome.converter_summaries.change[2] -ne 0 -or ($oldOutcome.warning_codes.change -join ',') -ne '108,172' -or -not $childRunLog.Contains('(warning #172) No reorder data defined. ROSIZ ignored. TEACH-DU-01 / BASE-01')){throw 'excluded diagnostic lineage differs'}
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false;$runCreated=$false;$sealed=$false;$fatal=$null
try {
  try{$acquired=$queue.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
  if(-not $acquired){throw 'host-wide native queue busy'}
  $gui=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -ne 1){throw 'expected protected GUI only'}
  $script:guiStart=$gui[0].StartTime.ToUniversalTime().ToString('o');$script:guiSession=$gui[0].SessionId
  $sessions=@(qwinsta 2>&1)
  if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {$_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)')}).Count -ne 1){throw 'GUI session not active'}
  function Assert-Gui {
    $p=@(Get-Process Simlox -ErrorAction SilentlyContinue)
    if($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $script:guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $script:guiStart){throw 'protected GUI changed'}
  }
  function Assert-Child([int]$childPid,[string]$needle){
    $w=Get-CimInstance Win32_Process -Filter "ProcessId=$childPid";$p=Get-Process -Id $childPid -ErrorAction Stop
    if(-not $w -or $w.Name -ne 'Simlox.exe' -or $p.SessionId -ne 0 -or -not $w.CommandLine.Contains($needle)){throw 'native child identity differs'}
  }
  New-Item -ItemType Directory -Path $run -ErrorAction Stop | Out-Null;$runCreated=$true
  $before=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$before[$entry.Key]=$entry.Value[1]};$before.runner=Hash $PSCommandPath;$before.python=Hash $python
  $report=Join-Path $run 'child-report-raw.json';$log=Join-Path $run 'child-report-export.log'
  $argsText=('"{0}" -silent -report -rpts "{1}" -rjexport "{2}" -log "{3}" -close' -f $sources.child_sxo[0],$settings,$report,$log)
  [ordered]@{schema='simlox-i07-var10-report-only-invocation/ssh-cli-v1';run_id=$RunId;parent_run_id=$old.run_id;parent_closure_sha256=$sources.diagnostic_closure[1];created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';arguments=$argsText;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $step=[ordered]@{name='child_report_only';arguments=$argsText;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;status='started';gui_preserved=$false;error=$null}
  $errorText=$null;$child=$null
  try {
    Assert-Gui
    $child=Start-Process -FilePath $exe -ArgumentList $argsText -WorkingDirectory $work -WindowStyle Hidden -PassThru
    if(-not $child.WaitForExit(60000)){
      Assert-Child $child.Id $log;Stop-Process -Id $child.Id -Force -ErrorAction Stop;$null=$child.WaitForExit(10000)
      throw 'report-only watchdog timeout after 60 seconds'
    }
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
  try{Assert-ParentRaw}catch{$errorText=$_.Exception.Message}
  [ordered]@{status=$step.status;error=$errorText;exit_code=$step.exit_code} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-i07-var10-report-only-closure/v1';run_id=$RunId;parent_run_id=$old.run_id;parent_closure_sha256=$sources.diagnostic_closure[1];invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;error=$errorText;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true
  if($errorText){throw $errorText}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;step='child_report_only';status='completed'} | ConvertTo-Json)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-i07-var10-report-only-closure/v1';run_id=$RunId;raw=$raw;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

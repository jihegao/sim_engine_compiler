param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$parent=Join-Path (Split-Path $case -Parent) 'J05-collection-window-v1.0.1\runs\j05-baseline-v101-20261001-01'
$parentPackage=Split-Path (Split-Path $parent -Parent) -Parent
$run=Join-Path (Join-Path $case 'runs') $RunId
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'80d6fe01b53ab2573405e79e34aebf4db859d7a303bcd04b55d9df43c9f368d4')
  parent_closure=@((Join-Path $parent 'closure.json'),'544ac02924741dae7f002b6bc3bb5c3002fe6b2d0f4a4cdd88088c5d5fd3c5ad')
  parent_input=@((Join-Path $parentPackage 'baseline-input.json'),'8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7')
  parent_sxo=@((Join-Path $parent 'model.sxo'),'d0f7290327d70c17c1bc6d41c3a19ba966773d58d7c9b587770a89def7f506a7')
  parent_report=@((Join-Path $parent 'report-raw.json'),'b9b7d970e7f12763f0098eb2d2c546cc2ed2b68792840e74f2175fcd4ca14099')
  parent_signoff=@((Join-Path $parentPackage 'cli-scope-signoff-2026-10-01.md'),'8c30b1b1a563c2350431fe7978eea12ae8c33bd112584dc3b53006d509ba9e95')
  settings_builder=@((Join-Path $case 'make_report_settings.py'),'695c6f932a1a60ad6daf2d12e43ece8bc45ebd92a100c56950b429d94702d354')
  mission_settings=@((Join-Path $case 'runs\settings\mission-enabled.sxs'),'ce17b329540fadf72b6256c9ead15913ce853bf847b5d09a2ef98cf56a6c57e5')
  default_settings=@('C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs','1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d')
  manual=@('C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf','39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
}
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Assert-Gui {
  $p=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $script:guiSession -or
     $p[0].StartTime.ToUniversalTime().ToString('o') -ne $script:guiStart){throw 'protected GUI changed'}
}
function Assert-Child([int]$childPid,[string]$needle){
  $w=Get-CimInstance Win32_Process -Filter "ProcessId=$childPid"
  $p=Get-Process -Id $childPid -ErrorAction Stop
  if(-not $w -or $w.Name -ne 'Simlox.exe' -or $p.SessionId -ne 0 -or -not $w.CommandLine.Contains($needle)){throw 'native report child identity differs'}
}
function Save-Steps {ConvertTo-Json -InputObject $script:steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8}
function Run-Report([string]$name,[string]$settings){
  $report=Join-Path $run "$name-report-raw.json"
  $log=Join-Path $run "$name-report-export.log"
  $arguments=('"{0}" -silent -report -rpts "{1}" -rjexport "{2}" -log "{3}" -close' -f (Join-Path $parent 'model.sxo'),$settings,$report,$log)
  $step=[ordered]@{name=$name;arguments=$arguments;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;status='started';gui_preserved=$false;error=$null}
  $child=$null
  try {
    Assert-Gui
    $child=Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru
    if(-not $child.WaitForExit(60000)){
      Assert-Child $child.Id $log
      Stop-Process -Id $child.Id -Force -ErrorAction Stop
      $null=$child.WaitForExit(10000)
      throw "$name report watchdog timeout after 60 seconds"
    }
    $step.exit_code=$child.ExitCode
    Assert-Gui;$step.gui_preserved=$true
    if($step.exit_code -ne 0){throw "$name report exit=$($step.exit_code)"}
    if(-not(Test-Path -LiteralPath $report) -or (Get-Item -LiteralPath $report).Length -le 1000){throw "$name report missing or too small"}
    if(-not(Test-Path -LiteralPath $log) -or (Get-Item -LiteralPath $log).Length -le 4){throw "$name report export log missing"}
    $step.status='completed'
  } catch {$step.status='failed';$step.error=$_.Exception.Message;throw}
  finally {
    if($child){$child.Refresh();if(-not $child.HasExited){try{Assert-Child $child.Id $log;Stop-Process -Id $child.Id -Force -ErrorAction Stop}catch{Write-Error "emergency native child cleanup failed: $($_.Exception.Message)"}}}
    $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o');$script:steps += $step;Save-Steps
  }
}
if(-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME){throw 'session-0 SSH required'}
if($RunId -ne 'k09-var01-report-settings-v100-ssh-20261004-01'){throw 'run ID differs from frozen contract'}
if(Test-Path -LiteralPath $run){throw 'immutable report run already exists'}
if(-not(Test-Path -LiteralPath $workingDirectory)){throw 'pinned working directory absent'}
$ancestors=@();$ancestorPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $ancestorPid -gt 0;$depth++){
  $ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if(-not $ancestor){break};$ancestors += $ancestor.Name;$ancestorPid=$ancestor.ParentProcessId
}
if($ancestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
& $python (Join-Path $case 'make_report_settings.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen settings builder failed'}
foreach($entry in $sources.GetEnumerator()){
  $path,$expected=$entry.Value
  if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}
}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$parentClosure=Get-Content -LiteralPath (Join-Path $parent 'closure.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'K09' -or $contract.variant_id -ne 'K09.var01' -or $contract.run_id -ne $RunId -or $parentClosure.error -or
   $contract.parent.input_sha256 -ne $sources.parent_input[1] -or
   $contract.parent.sxo_sha256 -ne $parentClosure.raw.'model.sxo'.sha256 -or
   $contract.parent.default_report_sha256 -ne $parentClosure.raw.'report-raw.json'.sha256 -or
   $contract.settings.mission_enabled_sha256 -ne $sources.mission_settings[1]){throw 'parent closure or frozen contract differs'}
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false;$created=$false;$sealed=$false;$steps=@();$fatalError=$null
try {
  try{$acquired=$queue.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
  if(-not $acquired){throw 'host-wide native queue busy'}
  $existing=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -le 0){throw 'expected protected GUI only'}
  $script:guiSession=$existing[0].SessionId;$script:guiStart=$existing[0].StartTime.ToUniversalTime().ToString('o')
  $sessions=@(qwinsta 2>&1)
  if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {$_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)')}).Count -ne 1){throw 'GUI session not active'}
  New-Item -ItemType Directory -Path $run -ErrorAction Stop | Out-Null;$created=$true
  $before=[ordered]@{}
  foreach($entry in $sources.GetEnumerator()){$before[$entry.Key]=$entry.Value[1]}
  $before.report_runner=Hash $PSCommandPath;$before.python=Hash $python
  [ordered]@{schema='simlox-k09-report-settings-invocation/ssh-cli-v1';run_id=$RunId;parent_run_id=$contract.parent.run_id;created_utc=(Get-Date).ToUniversalTime().ToString('o');session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$workingDirectory;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{status='not_started';error=$null}
  try {
    Run-Report 'default-a' $sources.default_settings[0]
    Run-Report 'mission-enabled' $sources.mission_settings[0]
    Run-Report 'default-b' $sources.default_settings[0]
    $outcome.status='completed'
  } catch {$outcome.status='failed';$outcome.error=$_.Exception.Message}
  $after=[ordered]@{}
  foreach($entry in $sources.GetEnumerator()){$after[$entry.Key]=Hash $entry.Value[0]}
  $after.report_runner=Hash $PSCommandPath;$after.python=Hash $python
  foreach($key in $before.Keys){if($before[$key] -ne $after[$key]){$outcome.status='failed';$outcome.error="source changed during report run: $key"}}
  $outcome | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{}
  foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-k09-report-settings-closure/v1';run_id=$RunId;parent_closure_sha256=$sources.parent_closure[1];invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true
  if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;steps=$steps.Count;status=$outcome.status} | ConvertTo-Json)
} catch {$fatalError=$_.Exception.Message;throw}
finally {
  if($created -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try {
      $partial=[ordered]@{}
      foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
      [ordered]@{schema='simlox-k09-report-settings-closure/v1';run_id=$RunId;raw=$partial;error=$fatalError;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
    } catch {Write-Error "partial report closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}


param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$native=Join-Path (Join-Path $case 'runs') 'e09-backorder-priority-v101-ssh-20261004-01'
$run=Join-Path (Join-Path $case 'runs') $RunId
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'1b5ef8c1312ab444fdc40b697707cffa52515fbf2c12149b52187707b6ecaa57')
  native_closure=@((Join-Path $native 'closure.json'),'77634d18e49988534adff6f3a9ef9c32bcb85f12e65da5293fc2c088bcddc295')
  fifo_sxo=@((Join-Path $native 'fifo.sxo'),'c298b5c45f393d20fcd19e6db163ab26ed9d05a07854e4a88608502cd91351fa')
  priority_sxo=@((Join-Path $native 'priority.sxo'),'11b7a882bfe3b6615ce28bb56dcf7a8db3e6eabd1d31808e8bd550ec1b55c410')
  disabled_sxo=@((Join-Path $native 'disabled.sxo'),'02d7f2b0e9574d4b193da88256d6e1058ffcd3bcb7b510c2f1e9c6f7f76076a5')
  selector_depot=@((Join-Path $case 'runs\report-settings\depot-01.sxs'),'2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9')
  selector_base01=@((Join-Path $case 'runs\report-settings\base-01.sxs'),'10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b')
  selector_base02=@((Join-Path $case 'runs\report-settings\base-02.sxs'),'83dfecf3d1d88e56d776ecd84268d1a5728cee256b0dd0e5912bf3a5251589c4')
  selector_builder=@((Join-Path $case 'make_report_settings.py'),'a456460ca59796f8869442968bb5223d7770b07e9029b6ea0fc18055b80a4216')
  default=@('C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs','1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d')
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
  if(-not $w -or $w.Name -ne 'Simlox.exe' -or $p.SessionId -ne 0 -or
     -not $w.CommandLine.Contains($needle)){throw 'native report child identity differs'}
}
function Save-Steps {ConvertTo-Json -InputObject $script:steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8}
function Run-Report([string]$name,[string]$sxo,[string]$settings){
  $report=Join-Path $run "$name-item-report-raw.json"
  $log=Join-Path $run "$name-report-export.log"
  $arguments=('"{0}" -silent -report -rpts "{1}" -rjexport "{2}" -log "{3}" -close' -f $sxo,$settings,$report,$log)
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
if($RunId -ne 'e09-backorder-priority-v101-item-report-ssh-20261004-01'){throw 'run ID differs from frozen contract'}
if(Test-Path -LiteralPath $run){throw 'immutable report run already exists'}
if(-not(Test-Path -LiteralPath $workingDirectory)){throw 'pinned working directory absent'}
$ancestors=@();$ancestorPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $ancestorPid -gt 0;$depth++){
  $ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if(-not $ancestor){break};$ancestors += $ancestor.Name;$ancestorPid=$ancestor.ParentProcessId
}
if($ancestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
foreach($entry in $sources.GetEnumerator()){
  $path,$expected=$entry.Value
  if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}
}
& $python (Join-Path $case 'make_report_settings.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen selector builder failed'}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$nativeClosure=Get-Content -LiteralPath (Join-Path $native 'closure.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.selected_report_run_id -ne $RunId -or $contract.run_id -ne $nativeClosure.run_id -or
   $nativeClosure.error -or $nativeClosure.raw.'fifo.sxo'.sha256 -ne $sources.fifo_sxo[1] -or
   $nativeClosure.raw.'priority.sxo'.sha256 -ne $sources.priority_sxo[1] -or
   $nativeClosure.raw.'disabled.sxo'.sha256 -ne $sources.disabled_sxo[1] -or
   $contract.report_settings.selectors_sha256.'DEPOT-01' -ne $sources.selector_depot[1] -or
   $contract.report_settings.selectors_sha256.'BASE-01' -ne $sources.selector_base01[1] -or
   $contract.report_settings.selectors_sha256.'BASE-02' -ne $sources.selector_base02[1]){throw 'frozen report source or contract differs'}
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
  [ordered]@{schema='simlox-e09-selected-item-reports-invocation/ssh-cli-v1';run_id=$RunId;source_run_id=$nativeClosure.run_id;created_utc=(Get-Date).ToUniversalTime().ToString('o');session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$workingDirectory;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{status='not_started';error=$null}
  try {
    foreach($arm in @('fifo','priority','disabled')){
      foreach($station in @('DEPOT-01','BASE-01','BASE-02')){
        $name="$arm-$($station.ToLowerInvariant())"
        $selector=Join-Path $case "runs\report-settings\$($station.ToLowerInvariant()).sxs"
        Run-Report $name (Join-Path $native "$arm.sxo") $selector
      }
    }
    $outcome.status='completed'
  } catch {$outcome.status='failed';$outcome.error=$_.Exception.Message}
  $after=[ordered]@{}
  foreach($entry in $sources.GetEnumerator()){$after[$entry.Key]=Hash $entry.Value[0]}
  $after.report_runner=Hash $PSCommandPath;$after.python=Hash $python
  foreach($key in $before.Keys){if($before[$key] -ne $after[$key]){$outcome.status='failed';$outcome.error="source changed during report run: $key"}}
  $outcome | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{}
  foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-e09-selected-item-reports-closure/v1';run_id=$RunId;source_run_id=$nativeClosure.run_id;source_closure_sha256=$sources.native_closure[1];invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true
  if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;steps=$steps.Count;status=$outcome.status} | ConvertTo-Json)
} catch {$fatalError=$_.Exception.Message;throw}
finally {
  if($created -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try {
      $partial=[ordered]@{}
      foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
      [ordered]@{schema='simlox-e09-selected-item-reports-closure/v1';run_id=$RunId;raw=$partial;error=$fatalError;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
    } catch {Write-Error "partial report closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

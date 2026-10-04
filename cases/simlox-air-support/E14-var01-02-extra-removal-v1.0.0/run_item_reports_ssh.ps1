param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$native=Join-Path (Join-Path $case 'runs') 'e14-var01-02-two-sru-panel-v100-ssh-20261005-01'
$run=Join-Path (Join-Path $case 'runs') $RunId
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$arms=@('seed2-control','seed2-extra','seed3-control','seed3-extra','seed4-control','seed4-extra','seed5-control','seed5-extra','seed6-control','seed6-extra')
$items=@('TEACH-LRU-01','TEACH-SRU-01','TEACH-SRU-02')
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'609e94a618e149becc356cf6521d7b7b00c4a2d0ba86e09a23935983a7407650')
  native_closure=@((Join-Path $native 'closure.json'),'a89e5ef615ff2fb9f3eb5205e9d6e8b45a8770c755f42aec9d68a6155aef6bdb')
  selector_builder=@((Join-Path $case 'make_report_settings.py'),'0fa06a3b35bfc39b3b48a4c66519a4929275d5d7e97dc18afaca29647bb8032a')
  default=@('C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs','1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d')
  selector_lru=@((Join-Path $case 'runs\report-settings\teach-lru-01.sxs'),'10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b')
  selector_sru01=@((Join-Path $case 'runs\report-settings\teach-sru-01.sxs'),'2463703548adbbcf46199c3e8f08ea8e5a96a84875e04648475e87fdefb612ad')
  selector_sru02=@((Join-Path $case 'runs\report-settings\teach-sru-02.sxs'),'f6f320fe334bd7edb5b0c5b22cb672245f977b600ee3632f6757d9f569d16b8b')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
}
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Assert-Gui {
  $p=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $script:guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $script:guiStart){throw 'protected GUI changed'}
}
function Assert-Child([int]$childPid,[string]$needle){
  $w=Get-CimInstance Win32_Process -Filter "ProcessId=$childPid";$p=Get-Process -Id $childPid -ErrorAction Stop
  if(-not $w -or $w.Name -ne 'Simlox.exe' -or $p.SessionId -ne 0 -or -not $w.CommandLine.Contains($needle)){throw 'native report child identity differs'}
}
function Save-Steps {ConvertTo-Json -InputObject $script:steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8}
function Run-Report([string]$name,[string]$sxo,[string]$settings){
  $report=Join-Path $run "$name-item-report-raw.json";$log=Join-Path $run "$name-report-export.log"
  $arguments=('"{0}" -silent -report -rpts "{1}" -rjexport "{2}" -log "{3}" -close' -f $sxo,$settings,$report,$log)
  $step=[ordered]@{name=$name;arguments=$arguments;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;status='started';gui_preserved=$false;error=$null};$child=$null
  try {
    Assert-Gui
    $child=Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $work -WindowStyle Hidden -PassThru
    if(-not $child.WaitForExit(60000)){
      Assert-Child $child.Id $log;Stop-Process -Id $child.Id -Force -ErrorAction Stop;$null=$child.WaitForExit(10000)
      throw "$name watchdog timeout after 60 seconds"
    }
    $step.exit_code=$child.ExitCode;Assert-Gui;$step.gui_preserved=$true
    if($step.exit_code -ne 0){throw "$name exit=$($step.exit_code)"}
    if(-not(Test-Path -LiteralPath $report) -or (Get-Item -LiteralPath $report).Length -le 1000){throw "$name report missing or too small"}
    if(-not(Test-Path -LiteralPath $log) -or (Get-Item -LiteralPath $log).Length -le 4){throw "$name report log missing"}
    $step.status='completed'
  } catch {$step.status='failed';$step.error=$_.Exception.Message;throw}
  finally {
    if($child){$child.Refresh();if(-not $child.HasExited){try{Assert-Child $child.Id $log;Stop-Process -Id $child.Id -Force -ErrorAction Stop}catch{Write-Error "targeted child cleanup failed: $($_.Exception.Message)"}}}
    $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o');$script:steps += $step;Save-Steps
  }
}
if(-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME){throw 'session-0 SSH required'}
if($RunId -ne 'e14-var01-02-two-sru-panel-v100-item-report-ssh-20261005-01'){throw 'run ID differs from frozen contract'}
if(Test-Path -LiteralPath $run){throw 'immutable report run already exists'}
if(-not(Test-Path -LiteralPath $work)){throw 'pinned working directory absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $ancestor){break};$ancestors += $ancestor.Name;$parentPid=$ancestor.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
& $python (Join-Path $case 'make_report_settings.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen selector builder failed'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$nativeClosure=Get-Content -LiteralPath (Join-Path $native 'closure.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'E14' -or $contract.selected_report_run_id -ne $RunId -or $contract.run_id -ne $nativeClosure.run_id -or $nativeClosure.error -or $contract.report_settings.installed_default_sha256 -ne $sources.default[1]){throw 'frozen report source or contract differs'}
foreach($item in $items){$selector=Join-Path $case ("runs\report-settings\"+$item.ToLowerInvariant()+'.sxs');if($contract.report_settings.item_selector_sha256.$item -ne (Hash $selector)){throw "selector pin differs: $item"}}
foreach($arm in $arms){$source=Join-Path $native "$arm.sxo";if(-not(Test-Path -LiteralPath $source) -or (Hash $source) -ne $nativeClosure.raw."$arm.sxo".sha256){throw "native SXO seal differs: $arm"}}
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false;$created=$false;$sealed=$false;$steps=@();$fatal=$null
try {
  try{$acquired=$queue.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
  if(-not $acquired){throw 'host-wide native queue busy'}
  $existing=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -le 0){throw 'expected protected GUI only'}
  $script:guiSession=$existing[0].SessionId;$script:guiStart=$existing[0].StartTime.ToUniversalTime().ToString('o')
  $sessions=@(qwinsta 2>&1)
  if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {$_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)')}).Count -ne 1){throw 'GUI session not active'}
  New-Item -ItemType Directory -Path $run -ErrorAction Stop | Out-Null;$created=$true
  $before=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$before[$entry.Key]=$entry.Value[1]}
  foreach($arm in $arms){$before["${arm}_sxo"]=$nativeClosure.raw."$arm.sxo".sha256}
  $before.report_runner=Hash $PSCommandPath;$before.python=Hash $python
  [ordered]@{schema='simlox-e14-selected-item-reports-invocation/ssh-cli-v1';run_id=$RunId;source_run_id=$nativeClosure.run_id;created_utc=(Get-Date).ToUniversalTime().ToString('o');session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$work;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{status='not_started';error=$null}
  try {
    foreach($arm in $arms){foreach($item in $items){$name="$arm-$($item.ToLowerInvariant())";Run-Report $name (Join-Path $native "$arm.sxo") (Join-Path $case ("runs\report-settings\"+$item.ToLowerInvariant()+'.sxs'))}}
    $outcome.status='completed'
  } catch {$outcome.status='failed';$outcome.error=$_.Exception.Message}
  $after=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$after[$entry.Key]=Hash $entry.Value[0]};foreach($arm in $arms){$after["${arm}_sxo"]=Hash (Join-Path $native "$arm.sxo")};$after.report_runner=Hash $PSCommandPath;$after.python=Hash $python
  foreach($key in $before.Keys){if($before[$key] -ne $after[$key]){$outcome.status='failed';$outcome.error="source changed during report run: $key"}}
  $outcome | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-e14-selected-item-reports-closure/v1';run_id=$RunId;source_run_id=$nativeClosure.run_id;source_closure_sha256=$sources.native_closure[1];invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true;if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;steps=$steps.Count;status=$outcome.status} | ConvertTo-Json)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($created -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$partial=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-e14-selected-item-reports-closure/v1';run_id=$RunId;raw=$partial;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial report closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

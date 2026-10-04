param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$run=Join-Path (Join-Path $case 'runs') $RunId
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$itemParent=Join-Path (Split-Path $case -Parent) 'D02-var01-traditional-op-hours-v1.0.0'
$fmParent=Join-Path (Split-Path $case -Parent) 'D02-var02-failure-mode-calendar-v1.0.0'
$arms=@('item-seed1-control','item-seed1-factor4','item-seed2-control','item-seed2-factor4','item-seed3-control','item-seed3-factor4','fm-seed1-control','fm-seed1-factor4','fm-seed2-control','fm-seed2-factor4','fm-seed3-control','fm-seed3-factor4')
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'f4919da5c016e6344c9dde3ea26a15195489f5549a38f7f51c2048591014b89f')
  builder=@((Join-Path $case 'build.py'),'ae4e65e37dda14c8fa8dda4fff4e236cfd692904b6ad6817f50f3361f7746f9a')
  item_parent=@((Join-Path $itemParent 'native-input.json'),'9e6d264330c6f7b41752ed8b0c09a32ac45089cec9ec823ad5e3367ce7f348e2')
  fm_parent=@((Join-Path $fmParent 'native-input.json'),'23b550dbc4e0aea4d6d328fe4805a4eb50af81f3af54ccd6353e45bce933271b')
  'item-seed1-control'=@((Join-Path $case 'item-seed1-control-input.json'),'eebe636c5d78f09e28df7864af3357f057bd7b1e202df7bd904699e224b4f017')
  'item-seed1-factor4'=@((Join-Path $case 'item-seed1-factor4-input.json'),'f86b724d436c9368688a8c26b43a8a6d7a4d95a00ffa44ecc0988476fb424f13')
  'item-seed2-control'=@((Join-Path $case 'item-seed2-control-input.json'),'660b41c92c4ccb102cf62edaefbd6b6355d167a9ceec95a98846bd0bc40a4528')
  'item-seed2-factor4'=@((Join-Path $case 'item-seed2-factor4-input.json'),'50f60082e9bb6138802a026ab30ed2c6de4c3ffa35ad2e71e4f9ec8908da8bbc')
  'item-seed3-control'=@((Join-Path $case 'item-seed3-control-input.json'),'09556de3d1720090d27f8bb490a5b774d2dc9a2780657bc6c0aef659a1231b1b')
  'item-seed3-factor4'=@((Join-Path $case 'item-seed3-factor4-input.json'),'463b57598e55b9ae3e99633288585e4fbb2c1b42ebdaf4a245a6ad76f26d368c')
  'fm-seed1-control'=@((Join-Path $case 'fm-seed1-control-input.json'),'8e7dc236d707d4d80218953709ec31de57e87c5d30931ddbb068cafb16208f34')
  'fm-seed1-factor4'=@((Join-Path $case 'fm-seed1-factor4-input.json'),'23e42f242f7faa59859adcece2813303a23f192396aa57ff879dda9182d4576d')
  'fm-seed2-control'=@((Join-Path $case 'fm-seed2-control-input.json'),'63cfa9064256e5f43707ef97d2da4d15f0d7c92a0d458e808bf057741df281e5')
  'fm-seed2-factor4'=@((Join-Path $case 'fm-seed2-factor4-input.json'),'e750c318408638010da540d41e8bec7d954c5a9d6f8c5848ad650ebcc1432f3c')
  'fm-seed3-control'=@((Join-Path $case 'fm-seed3-control-input.json'),'1d82c10291a36f589b65afae35bd9da01458a9ce0eda789efa65bd5daa7a66db')
  'fm-seed3-factor4'=@((Join-Path $case 'fm-seed3-factor4-input.json'),'128df4308669db6f75066c34bfd1d3afc1cd22238b00e6c21d2002d5f68df4f8')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual=@($manual,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
}
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Assert-Gui {
  $p=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $script:guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $script:guiStart){throw 'protected GUI changed'}
}
function Assert-Child([int]$childPid,[string]$needle){
  $w=Get-CimInstance Win32_Process -Filter "ProcessId=$childPid";$p=Get-Process -Id $childPid -ErrorAction Stop
  if(-not $w -or $w.Name -ne 'Simlox.exe' -or $p.SessionId -ne 0 -or -not $w.CommandLine.Contains($needle)){throw 'native child identity differs'}
}
function Save-Steps {ConvertTo-Json -InputObject $script:steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8}
function Run-Simlox([string]$name,[string]$argumentLine,[string]$needle){
  $step=[ordered]@{name=$name;arguments=$argumentLine;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;status='started';gui_preserved=$false;error=$null};$child=$null
  try {
    Assert-Gui
    $child=Start-Process -FilePath $exe -ArgumentList $argumentLine -WorkingDirectory $work -WindowStyle Hidden -PassThru
    if(-not $child.WaitForExit(60000)){
      Assert-Child $child.Id $needle;Stop-Process -Id $child.Id -Force -ErrorAction Stop;$null=$child.WaitForExit(10000)
      throw "$name watchdog timeout after 60 seconds"
    }
    $step.exit_code=$child.ExitCode;Assert-Gui;$step.gui_preserved=$true
    if($step.exit_code -ne 0){throw "$name exit=$($step.exit_code)"}
    $step.status='completed'
  } catch {$step.status='failed';$step.error=$_.Exception.Message;throw}
  finally {
    if($child){$child.Refresh();if(-not $child.HasExited){try{Assert-Child $child.Id $needle;Stop-Process -Id $child.Id -Force -ErrorAction Stop}catch{Write-Error "targeted child cleanup failed: $($_.Exception.Message)"}}}
    $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o');$script:steps += $step;Save-Steps
  }
}
function Require-Size([string]$name,[int64]$min){$p=Join-Path $run $name;if(-not(Test-Path -LiteralPath $p) -or (Get-Item -LiteralPath $p).Length -le $min){throw "$name missing or too small"}}
if(-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME){throw 'session-0 SSH required'}
if($RunId -ne 'i06-var01-02-reliability-panel-v100-ssh-20261005-01'){throw 'run ID differs from contract'}
if(Test-Path -LiteralPath $run){throw 'immutable run directory already exists'}
if(-not(Test-Path -LiteralPath $work)){throw 'pinned working directory absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $ancestor){break};$ancestors += $ancestor.Name;$parentPid=$ancestor.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
& $python (Join-Path $case 'build.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen input builder verification failed'}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'I06' -or $contract.version -ne '1.0.0-candidate' -or $contract.run_id -ne $RunId -or $contract.dependency.item_parent_input_sha256 -ne $sources.item_parent[1] -or $contract.dependency.fm_parent_input_sha256 -ne $sources.fm_parent[1] -or $contract.manual.sha256 -ne $sources.manual[1]){throw 'frozen contract fields differ'}
foreach($arm in $arms){if($contract.inputs_sha256.$arm -ne $sources[$arm][1]){throw "contract input pin differs: $arm"}}
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false;$runCreated=$false;$sealed=$false;$steps=@();$fatal=$null
try {
  try{$acquired=$queue.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
  if(-not $acquired){throw 'host-wide native queue busy'}
  $existing=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -le 0){throw 'expected protected GUI only'}
  $script:guiSession=$existing[0].SessionId;$script:guiStart=$existing[0].StartTime.ToUniversalTime().ToString('o')
  $sessions=@(qwinsta 2>&1)
  if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {$_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)')}).Count -ne 1){throw 'GUI session not active'}
  New-Item -ItemType Directory -Path $run -ErrorAction Stop | Out-Null;$runCreated=$true
  foreach($arm in $arms){Copy-Item -LiteralPath (Join-Path $case "$arm-input.json") -Destination (Join-Path $run "$arm-input.json")}
  $before=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$before[$entry.Key]=$entry.Value[1]}
  $before.runner=Hash $PSCommandPath;$before.python=Hash $python
  [ordered]@{schema='simlox-i06-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$work;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{arms=[ordered]@{};converter_summaries=[ordered]@{};warning_codes=[ordered]@{};error=$null}
  foreach($arm in $arms){$outcome.arms[$arm]='not_started'}
  try {
    foreach($arm in $arms){
      $sxi=Join-Path $run "$arm.sxi";$sxo=Join-Path $run "$arm.sxo"
      Run-Simlox "${arm}_import" ('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run "$arm-input.json"),$sxi,(Join-Path $run "$arm-import.log")) (Join-Path $run "$arm-import.log")
      Require-Size "$arm.sxi" 4
      Run-Simlox "${arm}_export" ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run "$arm-roundtrip-raw.json"),(Join-Path $run "$arm-export.log")) (Join-Path $run "$arm-export.log")
      Require-Size "$arm-roundtrip-raw.json" 1000
      Run-Simlox "${arm}_calc" ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run "$arm-run.log")) (Join-Path $run "$arm-run.log")
      Require-Size "$arm-run.log" 4
      $log=Get-Content -LiteralPath (Join-Path $run "$arm-run.log") -Raw -Encoding UTF8
      $m=[regex]::Match($log,'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
      if(-not $m.Success){throw "$arm converter summary absent"}
      $outcome.converter_summaries[$arm]=@([int]$m.Groups[1].Value,[int]$m.Groups[2].Value,[int]$m.Groups[3].Value)
      $warningCodes=@([regex]::Matches($log,'\(warning #(\d+)\)') | ForEach-Object {$_.Groups[1].Value})
      $outcome.warning_codes[$arm]=$warningCodes
      if([int]$m.Groups[1].Value -ne 0 -or [int]$m.Groups[3].Value -ne 0 -or @($warningCodes | Where-Object {$_ -notin @('108','126')}).Count -gt 0){throw "$arm unreviewed converter diagnostic"}
      Require-Size "$arm.sxo" 4;Require-Size "$arm.log" 4
      Run-Simlox "${arm}_report" ('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,(Join-Path $run "$arm-report-raw.json"),(Join-Path $run "$arm-report-export.log")) (Join-Path $run "$arm-report-export.log")
      Require-Size "$arm-report-raw.json" 1000
      $outcome.arms[$arm]='completed'
    }
  } catch {$outcome.error=$_.Exception.Message}
  $after=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$after[$entry.Key]=Hash $entry.Value[0]};$after.runner=Hash $PSCommandPath;$after.python=Hash $python
  foreach($key in $before.Keys){if($before[$key] -ne $after[$key]){$outcome.error="source changed during run: $key"}}
  $outcome | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-i06-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true;if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;steps=$steps.Count;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$partial=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-i06-closure/v1';run_id=$RunId;raw=$partial;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

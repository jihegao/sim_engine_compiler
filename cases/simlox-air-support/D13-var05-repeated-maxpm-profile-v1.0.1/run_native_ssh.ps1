param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$run=Join-Path (Join-Path $case 'runs') $RunId
$parent=Join-Path (Split-Path $case -Parent) 'D13-var03-dynamic-maxpm-v1.0.0'
$parentRun=Join-Path (Join-Path $parent 'runs') 'd13-dynamic-maxpm-v100-ssh-20261004-01'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'00b14476e4d8f2dc2cee83a3da9f81501d9a59039f13b4349edf9025559d38a3')
  flat=@((Join-Path $case 'flat-input.json'),'fde24c914f94b2f945c3c55aa485972289ddc5e6ea449388bd22c25477977604')
  nested=@((Join-Path $case 'nested-input.json'),'e1e12abb2c82ef1ea3ca528702ed4d95aa41bd0de3bb14b75e907888c9013f10')
  parent_input=@((Join-Path $parent 'rise-input.json'),'3e9a0c1f79eb57ed0eeb054649e4d991e41e33d55eca3ee365c4df7260eb65f1')
  parent_closure=@((Join-Path $parentRun 'closure.json'),'252b24c67ceb3002cf6b210554f3415eb522862bf5c76c0036227c867cc9dc15')
  parent_signoff=@((Join-Path $parent 'cli-scope-signoff-2026-10-04.md'),'42336a825df7f4649164afe7502652172ec36fffbc0a72c2e6b761c1b0b4d999')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual=@($manual,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
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
     -not $w.CommandLine.Contains($needle)){throw 'native child identity differs'}
}
function Save-Steps {ConvertTo-Json -InputObject $script:steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8}
function Run-Simlox([string]$name,[string]$argumentLine,[string]$needle){
  $step=[ordered]@{name=$name;arguments=$argumentLine;working_directory=$workingDirectory;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;status='started';gui_preserved=$false;error=$null}
  $child=$null
  try {
    Assert-Gui
    $child=Start-Process -FilePath $exe -ArgumentList $argumentLine -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru
    if(-not $child.WaitForExit(60000)){
      Assert-Child $child.Id $needle
      Stop-Process -Id $child.Id -Force -ErrorAction Stop
      $null=$child.WaitForExit(10000)
      throw "$name watchdog timeout after 60 seconds"
    }
    $step.exit_code=$child.ExitCode
    Assert-Gui;$step.gui_preserved=$true
    if($step.exit_code -ne 0){throw "$name exit=$($step.exit_code)"}
    $step.status='completed'
  } catch {$step.status='failed';$step.error=$_.Exception.Message;throw}
  finally {
    if($child){$child.Refresh();if(-not $child.HasExited){try{Assert-Child $child.Id $needle;Stop-Process -Id $child.Id -Force -ErrorAction Stop}catch{Write-Error "emergency native child cleanup failed: $($_.Exception.Message)"}}}
    $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o');$script:steps += $step;Save-Steps
  }
}
function Require-Size([string]$name,[int64]$minimum){
  $p=Join-Path $run $name
  if(-not(Test-Path -LiteralPath $p) -or (Get-Item -LiteralPath $p).Length -le $minimum){throw "$name absent or too small"}
}
if(-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME){throw 'session-0 SSH required'}
if($RunId -ne 'd13-repeated-maxpm-profile-v101-ssh-20261004-01'){throw 'run ID differs from frozen contract'}
if(Test-Path -LiteralPath $run){throw 'immutable run directory already exists'}
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
& $python (Join-Path $case 'build.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen builder failed'}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'D13' -or $contract.variant_ids.Count -ne 1 -or $contract.variant_ids[0] -ne 'D13.var05' -or
   $contract.version -ne '1.0.1-candidate' -or $contract.run_id -ne $RunId -or
   $contract.inputs_sha256.flat -ne $sources.flat[1] -or
   $contract.inputs_sha256.nested -ne $sources.nested[1] -or
   $contract.dependency.parent_input_sha256 -ne $sources.parent_input[1] -or
   $contract.dependency.parent_closure_sha256 -ne $sources.parent_closure[1] -or
   $contract.dependency.parent_signoff_sha256 -ne $sources.parent_signoff[1] -or
   $contract.manual.sha256 -ne $sources.manual[1]){throw 'frozen contract fields differ'}
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false;$runCreated=$false;$sealed=$false;$steps=@();$fatalError=$null
try {
  try{$acquired=$queue.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
  if(-not $acquired){throw 'host-wide native queue busy'}
  $existing=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -le 0){throw 'expected protected GUI only'}
  $script:guiSession=$existing[0].SessionId;$script:guiStart=$existing[0].StartTime.ToUniversalTime().ToString('o')
  $sessions=@(qwinsta 2>&1)
  if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {$_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)')}).Count -ne 1){throw 'GUI session not active'}
  New-Item -ItemType Directory -Path $run -ErrorAction Stop | Out-Null;$runCreated=$true
  foreach($arm in @('flat','nested')){Copy-Item -LiteralPath (Join-Path $case "$arm-input.json") -Destination (Join-Path $run "$arm-input.json")}
  $sourceHashes=[ordered]@{}
  foreach($entry in $sources.GetEnumerator()){$sourceHashes[$entry.Key]=$entry.Value[1]}
  foreach($name in @('build.py','run_native_ssh.ps1')){$sourceHashes[$name]=Hash (Join-Path $case $name)}
  $sourceHashes.python=Hash $python
  [ordered]@{schema='simlox-d13-repeated-maxpm-profile-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$workingDirectory;source_hashes_before=$sourceHashes;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{flat='not_started';nested='not_started';converter_summaries=[ordered]@{};error=$null}
  try {
    foreach($arm in @('flat','nested')){
      $sxi=Join-Path $run "$arm.sxi";$sxo=Join-Path $run "$arm.sxo"
      Run-Simlox "${arm}_import" ('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run "$arm-input.json"),$sxi,(Join-Path $run "$arm-import.log")) (Join-Path $run "$arm-import.log")
      Require-Size "$arm.sxi" 4
      Run-Simlox "${arm}_export" ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run "$arm-roundtrip-raw.json"),(Join-Path $run "$arm-export.log")) (Join-Path $run "$arm-export.log")
      Require-Size "$arm-roundtrip-raw.json" 1000
      Run-Simlox "${arm}_calc" ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run "$arm-run.log")) (Join-Path $run "$arm-run.log")
      Require-Size "$arm-run.log" 4
      $calcLog=Get-Content -LiteralPath (Join-Path $run "$arm-run.log") -Raw -Encoding UTF8
      $match=[regex]::Match($calcLog,'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
      if(-not $match.Success){throw "$arm converter summary absent"}
      $outcome.converter_summaries[$arm]=@([int]$match.Groups[1].Value,[int]$match.Groups[2].Value,[int]$match.Groups[3].Value)
      if([int]$match.Groups[1].Value -ne 0){throw "$arm converter errors=$($match.Groups[1].Value)"}
      Require-Size "$arm.sxo" 4;Require-Size "$arm.log" 4
      Run-Simlox "${arm}_report" ('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,(Join-Path $run "$arm-report-raw.json"),(Join-Path $run "$arm-report-export.log")) (Join-Path $run "$arm-report-export.log")
      Require-Size "$arm-report-raw.json" 1000
      $outcome[$arm]='completed'
    }
  } catch {$outcome.error=$_.Exception.Message}
  $sourceHashesAfter=[ordered]@{}
  foreach($entry in $sources.GetEnumerator()){$sourceHashesAfter[$entry.Key]=Hash $entry.Value[0]}
  foreach($name in @('build.py','run_native_ssh.ps1')){$sourceHashesAfter[$name]=Hash (Join-Path $case $name)}
  $sourceHashesAfter.python=Hash $python
  foreach($key in $sourceHashes.Keys){if($sourceHashes[$key] -ne $sourceHashesAfter[$key]){$outcome.error="source changed during run: $key"}}
  $outcome | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{}
  foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-d13-repeated-maxpm-profile-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$sourceHashes;source_hashes_after=$sourceHashesAfter;raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true
  if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatalError=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try {
      $partial=[ordered]@{}
      foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
      [ordered]@{schema='simlox-d13-repeated-maxpm-profile-closure/v1';run_id=$RunId;invocation_sha256=$(if(Test-Path -LiteralPath (Join-Path $run 'invocation.json')){Hash (Join-Path $run 'invocation.json')}else{$null});raw=$partial;error=$fatalError;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
    } catch {Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

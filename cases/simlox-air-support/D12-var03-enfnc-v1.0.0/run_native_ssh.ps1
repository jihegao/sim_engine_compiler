param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$run=Join-Path (Join-Path $case 'runs') $RunId
$parent=Join-Path (Split-Path $case -Parent) 'D08-var03-criticality-v1.0.0'
$parentRun=Join-Path (Join-Path $parent 'runs') 'd08-var03-failure-mode-v100-ssh-20261002-01'
$pattern=Join-Path (Split-Path $case -Parent) 'D05-maintenance-competition-v1.0.0'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'84e005b1948f09ddb74eb8cc26afcd7053832a259123933c0a3e9c041c41896d')
  n=@((Join-Path $case 'n-input.json'),'76d633d9461ce0f10aba9b88327ac4e2b510d48a4f947051e181c7e77e8b2834')
  y=@((Join-Path $case 'y-input.json'),'149e4d5b2dd7e50e8aff33aae02ad58cf125925df5ce94fa54f61484e989d662')
  parent_input=@((Join-Path $parent 'native-input-failure-mode.json'),'36d20f6be3bcb877ff925542aa2a3f95324a7e1562ed57f18c1561fba27fe59e')
  parent_closure=@((Join-Path $parentRun 'closure.json'),'47a0f9aa98a0682afa4a997de86e880ea0f9e654cee16587b9f6e309d8196fbe')
  parent_signoff=@((Join-Path $parent 'cli-scope-signoff-2026-10-02.md'),'ace40efeac9e2b2854f0d56a2635b397c8988db6b882bc6d91645539b3237749')
  pattern_input=@((Join-Path $pattern 'native-input.json'),'4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad')
  pattern_signoff=@((Join-Path $pattern 'cli-scope-signoff-2026-09-30.md'),'e645b900f397a955d2b588aa5f0e4d50f2f4b7d082a09f35e7b89a4dfaf23c11')
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
if($RunId -ne 'd12-var03-enfnc-v100-ssh-20261004-01'){throw 'run ID differs from frozen contract'}
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
if($contract.case_id -ne 'D12' -or $contract.variant_id -ne 'D12.var03' -or
   $contract.version -ne '1.0.0-candidate' -or $contract.run_id -ne $RunId -or
   $contract.inputs_sha256.n -ne $sources.n[1] -or
   $contract.inputs_sha256.y -ne $sources.y[1] -or
   $contract.dependency.input_sha256 -ne $sources.parent_input[1] -or
   $contract.dependency.closure_sha256 -ne $sources.parent_closure[1] -or
   $contract.dependency.signoff_sha256 -ne $sources.parent_signoff[1] -or
   $contract.dependency.maintenance_pattern_input_sha256 -ne $sources.pattern_input[1] -or
   $contract.dependency.maintenance_pattern_signoff_sha256 -ne $sources.pattern_signoff[1]){throw 'frozen contract fields differ'}
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
  foreach($arm in @('n','y')){Copy-Item -LiteralPath (Join-Path $case "$arm-input.json") -Destination (Join-Path $run "$arm-input.json")}
  $sourceHashes=[ordered]@{}
  foreach($entry in $sources.GetEnumerator()){$sourceHashes[$entry.Key]=$entry.Value[1]}
  foreach($name in @('build.py','run_native_ssh.ps1')){$sourceHashes[$name]=Hash (Join-Path $case $name)}
  $sourceHashes.python=Hash $python
  [ordered]@{schema='simlox-d12-enfnc-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$workingDirectory;source_hashes_before=$sourceHashes;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{n='not_started';y='not_started';converter_summaries=[ordered]@{};error=$null}
  try {
    foreach($arm in @('n','y')){
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
  [ordered]@{schema='simlox-d12-enfnc-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$sourceHashes;source_hashes_after=$sourceHashesAfter;raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true
  if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatalError=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try {
      $partial=[ordered]@{}
      foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
      [ordered]@{schema='simlox-d12-enfnc-closure/v1';run_id=$RunId;invocation_sha256=$(if(Test-Path -LiteralPath (Join-Path $run 'invocation.json')){Hash (Join-Path $run 'invocation.json')}else{$null});raw=$partial;error=$fatalError;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
    } catch {Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

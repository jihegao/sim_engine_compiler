param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$run=Join-Path (Join-Path $case 'runs') $RunId
$parent=Join-Path (Split-Path $case -Parent) 'K02-var01-json-structure-v1.0.1'
$parentRun=Join-Path (Join-Path $parent 'runs') 'k02-var01-named-v101-ssh-20261004-01'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'198832616cd9cf79d1699f8e0bfc94ee0db01ba1fa3d9e57168a4be1ca909418')
  normal=@((Join-Path $case 'normal-input.json'),'b94e367d46665d4d58f2fb8d15771a61a6d51369070db85ab9bda851c3e76b00')
  inactive_base=@((Join-Path $case 'inactive-base-input.json'),'b163f2c5beb1429edccd492d99e59beb6b14b56d513b7fe569811500094c69e8')
  parent_input=@((Join-Path $parent 'named-input.json'),'b94e367d46665d4d58f2fb8d15771a61a6d51369070db85ab9bda851c3e76b00')
  parent_sxi=@((Join-Path $parentRun 'model.sxi'),'60c7a5cddd2af357282d948aa92409f526d751a173b19c931f9a5213f83e8815')
  parent_closure=@((Join-Path $parentRun 'closure.json'),'86e93d3fc94dcae4b034432b2ccea16e84c7b3e17894d3e5ea6ef1bdb2b999c3')
  parent_signoff=@((Join-Path $parent 'cli-scope-signoff-2026-10-04.md'),'e4f14cbdb2e74237189a46d2a743101b4033a0f3d59c38619ca7eb208ca67e89')
  parent_log=@((Join-Path $parentRun 'model.log'),'2d2e6c368305203052e347748dab8f36261947dae6f6a189fad4312e47c0a491')
  parent_report=@((Join-Path $parentRun 'report-raw.json'),'5a3fd9007de442ce0f7a5210cd61cfe1e3a362774300497020341dc05d478655')
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
if($RunId -ne 'k07-var02-cli-evidence-v100-ssh-20261004-01'){throw 'run ID differs from frozen contract'}
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
if($contract.case_id -ne 'K07' -or $contract.version -ne '1.0.0-candidate' -or
   $contract.run_id -ne $RunId -or ($contract.variant_ids -join ',') -ne 'K07.var02,K07.var03,K07.var05' -or
   $contract.inputs_sha256.normal -ne $sources.normal[1] -or
   $contract.inputs_sha256.inactive_base -ne $sources.inactive_base[1] -or
   $contract.dependency.closure_sha256 -ne $sources.parent_closure[1]){throw 'frozen contract fields differ'}
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
  Copy-Item -LiteralPath (Join-Path $case 'normal-input.json') -Destination (Join-Path $run 'normal-input.json')
  Copy-Item -LiteralPath (Join-Path $case 'inactive-base-input.json') -Destination (Join-Path $run 'inactive-base-input.json')
  $sourceHashes=[ordered]@{}
  foreach($entry in $sources.GetEnumerator()){$sourceHashes[$entry.Key]=$entry.Value[1]}
  foreach($name in @('build.py','run_native_ssh.ps1')){$sourceHashes[$name]=Hash (Join-Path $case $name)}
  $sourceHashes.python=Hash $python
  [ordered]@{schema='simlox-k07-cli-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$workingDirectory;source_hashes_before=$sourceHashes;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{normal='not_started';copy_convert='not_started';inactive_base='not_started';negative_converter_summary=$null;negative_sxo_bytes=$null;error=$null}
  try {
    $normal=Join-Path $run 'normal.sxi';$normalSxo=Join-Path $run 'normal.sxo'
    Run-Simlox 'normal_import' ('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'normal-input.json'),$normal,(Join-Path $run 'normal-import.log')) (Join-Path $run 'normal-import.log')
    Require-Size 'normal.sxi' 4;Require-Size 'normal-import.log' 4
    Run-Simlox 'normal_export' ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $normal,(Join-Path $run 'normal-roundtrip-raw.json'),(Join-Path $run 'normal-export.log')) (Join-Path $run 'normal-export.log')
    Require-Size 'normal-roundtrip-raw.json' 1000
    Run-Simlox 'normal_calc' ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $normal,(Join-Path $run 'normal-run.log')) (Join-Path $run 'normal-run.log')
    Require-Size 'normal.sxo' 4;Require-Size 'normal.log' 4
    $normalRunLog=Get-Content -LiteralPath (Join-Path $run 'normal-run.log') -Raw -Encoding UTF8
    if($normalRunLog -notmatch 'Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0' -or
       (@([regex]::Matches($normalRunLog,'\(warning #(\d+)\)') | ForEach-Object {$_.Groups[1].Value}) -join ',') -ne '108,126' -or
       $normalRunLog -match '\(error #'){throw 'normal converter diagnostics differ'}
    Run-Simlox 'normal_report' ('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $normalSxo,(Join-Path $run 'normal-report-raw.json'),(Join-Path $run 'normal-report-export.log')) (Join-Path $run 'normal-report-export.log')
    Require-Size 'normal-report-raw.json' 1000
    $outcome.normal='completed'
    Copy-Item -LiteralPath $normal -Destination (Join-Path $run 'convert-copy.sxi')
    $originalSxiHash=Hash $normal
    $copy=Join-Path $run 'convert-copy.sxi'
    Run-Simlox 'copy_convert' ('"{0}" -silent -convert -log "{1}" -close' -f $copy,(Join-Path $run 'convert.log')) (Join-Path $run 'convert.log')
    Require-Size 'convert-copy.sxi' 4
    if((Hash $normal) -ne $originalSxiHash){throw 'original SXI changed during copy conversion'}
    Run-Simlox 'copy_export' ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $copy,(Join-Path $run 'convert-roundtrip-raw.json'),(Join-Path $run 'convert-export.log')) (Join-Path $run 'convert-export.log')
    Require-Size 'convert-roundtrip-raw.json' 1000
    $outcome.copy_convert='completed'
    $negative=Join-Path $run 'inactive-base.sxi';$negativeSxo=Join-Path $run 'inactive-base.sxo'
    Run-Simlox 'inactive_base_import' ('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'inactive-base-input.json'),$negative,(Join-Path $run 'inactive-base-import.log')) (Join-Path $run 'inactive-base-import.log')
    Require-Size 'inactive-base.sxi' 4
    Run-Simlox 'inactive_base_export' ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $negative,(Join-Path $run 'inactive-base-roundtrip-raw.json'),(Join-Path $run 'inactive-base-export.log')) (Join-Path $run 'inactive-base-export.log')
    Require-Size 'inactive-base-roundtrip-raw.json' 1000
    Run-Simlox 'inactive_base_calc' ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $negative,(Join-Path $run 'inactive-base-run.log')) (Join-Path $run 'inactive-base-run.log')
    Require-Size 'inactive-base-run.log' 4
    $negativeLog=Get-Content -LiteralPath (Join-Path $run 'inactive-base-run.log') -Raw -Encoding UTF8
    $match=[regex]::Match($negativeLog,'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
    if(-not $match.Success){throw 'negative converter summary absent'}
    $outcome.negative_converter_summary=@([int]$match.Groups[1].Value,[int]$match.Groups[2].Value,[int]$match.Groups[3].Value)
    $outcome.negative_sxo_bytes=$(if(Test-Path -LiteralPath $negativeSxo){(Get-Item -LiteralPath $negativeSxo).Length}else{$null})
    if([int]$match.Groups[1].Value -le 0 -or $outcome.negative_sxo_bytes -ne 4){throw 'negative hypothesis failed: expected conversion error and four-byte SXO'}
    $outcome.inactive_base='completed_rejection'
  } catch {$outcome.error=$_.Exception.Message}
  $sourceHashesAfter=[ordered]@{}
  foreach($entry in $sources.GetEnumerator()){$sourceHashesAfter[$entry.Key]=Hash $entry.Value[0]}
  foreach($name in @('build.py','run_native_ssh.ps1')){$sourceHashesAfter[$name]=Hash (Join-Path $case $name)}
  $sourceHashesAfter.python=Hash $python
  foreach($key in $sourceHashes.Keys){if($sourceHashes[$key] -ne $sourceHashesAfter[$key]){$outcome.error="source changed during run: $key"}}
  $outcome | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{}
  foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-k07-cli-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$sourceHashes;source_hashes_after=$sourceHashesAfter;raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true
  if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatalError=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try {
      $partial=[ordered]@{}
      foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
      [ordered]@{schema='simlox-k07-cli-closure/v1';run_id=$RunId;invocation_sha256=$(if(Test-Path -LiteralPath (Join-Path $run 'invocation.json')){Hash (Join-Path $run 'invocation.json')}else{$null});raw=$partial;error=$fatalError;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
    } catch {Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference='Stop'
Set-Content -LiteralPath (Join-Path $PSScriptRoot 'preflight.trace') -Value 'entered' -Encoding Ascii
Write-Output 'K04.var04 preflight: script entered'
$case=(Resolve-Path $PSScriptRoot).Path
$run=Join-Path (Join-Path $case 'runs') $RunId
$parent=Join-Path (Split-Path $case -Parent) 'K04-var01-nested-mdb-include-v1.0.0'
$parentRun=Join-Path (Join-Path $parent 'runs') 'k04-var01-nested-mdb-v100-ssh-20261004-01'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$ps32='C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$associationPath='HKCU:\Software\Systecon\SIMLOX Version 2017\Database Associations'
$associationOriginal='mdb=Microsoft Access Driver (*.mdb)|'
$associationTemporary='mdb=Microsoft Access Driver (*.mdb, *.accdb)|'
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'060e3f469e375b44b36d4767f9db1d5b74c61473a9b0530bc819ebb29e18b28d')
  control_main=@((Join-Path $case 'control-main-input.json'),'341597dd22c735049d619b7ca11e7655e14d3848ddfba7e68b81527b841d6d9a')
  key_main=@((Join-Path $case 'key-main-input.json'),'1377d074140da59ce9e7dddf7f534859520d98969f3c8fe6e773568249765bab')
  control_mdb_source=@((Join-Path $case 'control-mdb-source.json'),'ef7e2ac537f5b92884c9542ef7920c5b150bdfa4a523a56f039c05e36b4e92b4')
  key_level1_source=@((Join-Path $case 'key-level1-source.json'),'cf5eb1e9fbf7768e51e852947b6cf0f749e6c147c01a4294bd49b5c0ad6286a6')
  key_level2_source=@((Join-Path $case 'key-level2-source.json'),'4a38dde128264c57ec195e952b2f4f2e67a53404d2899ba99cb1d8ac263df093')
  accepted_parent_main=@((Join-Path $parent 'main-input.json'),'aa0064561c2a1aa9738422c8090ca125478c0517e16010022634bd985da6fa52')
  accepted_parent_station=@((Join-Path $parent 'level2-source.json'),'2c2fc671f6084ce90a4635526e50dc6df4b7ebd087c8fd8eca4080839c5a3ddb')
  accepted_parent_closure=@((Join-Path $parentRun 'closure.json'),'e8530f8e5cd65f788b70596e5f755f0b84ae350b66b7cff8746de36f23e3c0d0')
  accepted_parent_signoff=@((Join-Path $parent 'cli-scope-signoff-2026-10-04.md'),'b508239bff323d4155bfb5ec10f3e8e3921d30e7ed6720cc5d42ce5b14d9d4ee')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual=@($manual,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
}
function Hash([string]$path){return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Assert-Gui {
  $p=@(Get-Process Simlox -ErrorAction SilentlyContinue | Where-Object {$_.Id -eq 13340})
  if($p.Count -ne 1 -or $p[0].SessionId -ne $script:guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $script:guiStart){throw 'protected GUI process changed'}
}
function Assert-Child([int]$childPid,[string]$sxi){
  $w=Get-CimInstance Win32_Process -Filter "ProcessId=$childPid"
  $p=Get-Process -Id $childPid -ErrorAction Stop
  if(-not $w -or $w.Name -ne 'Simlox.exe' -or $p.SessionId -ne 0 -or -not $w.CommandLine.Contains($sxi)){throw 'native child identity differs'}
}
function Record-Step($step){
  $script:steps += $step
  ConvertTo-Json -InputObject $script:steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
}
function Run-Generator([string]$kind,[string]$source,[string]$output){
  $arguments=@('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $case 'create_mdb_x86.ps1'),'-Kind',$kind,'-Source',$source,'-Output',$output)
  $step=[ordered]@{name="create_$kind";arguments=$arguments;working_directory=$run;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;status='started';gui_preserved=$false;error=$null}
  try {
    Assert-Gui
    & $ps32 @arguments
    $step.exit_code=$LASTEXITCODE
    Assert-Gui; $step.gui_preserved=$true
    if($step.exit_code -ne 0){throw "MDB generator $kind exit=$($step.exit_code)"}
    if((Get-Item -LiteralPath $output).Length -le 4 -or (Get-Item -LiteralPath ([IO.Path]::ChangeExtension($output,'.readback.json'))).Length -le 4){throw "MDB/readback empty for $kind"}
    $step.status='completed'
  } catch {$step.status='failed';$step.error=$_.Exception.Message;throw}
  finally {$step.completed_utc=(Get-Date).ToUniversalTime().ToString('o');Record-Step $step}
}
function Run-Simlox([string]$name,[string]$argumentLine,[string]$sxi,[bool]$useMdb){
  $step=[ordered]@{name=$name;arguments=$argumentLine;working_directory=$workingDirectory;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;status='started';gui_preserved=$false;error=$null}
  $child=$null
  try {
    Assert-Gui
    if($useMdb){
      $script:associationChanged=$true
      Set-ItemProperty -LiteralPath $associationPath -Name ListOfAssociations -Value $associationTemporary
      if((Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations) -cne $associationTemporary){throw 'temporary MDB association did not apply'}
    }
    $child=Start-Process -FilePath $exe -ArgumentList $argumentLine -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru
    if(-not $child.WaitForExit(60000)){
      Assert-Child $child.Id $sxi
      Stop-Process -Id $child.Id -Force -ErrorAction Stop
      $null=$child.WaitForExit(10000)
      throw "$name watchdog timeout after 60 seconds"
    }
    $step.exit_code=$child.ExitCode
    Assert-Gui; $step.gui_preserved=$true
    if($step.exit_code -ne 0){throw "$name exit=$($step.exit_code)"}
    $step.status='completed'
  } catch {$step.status='failed';$step.error=$_.Exception.Message;throw}
  finally {
    if($child){$child.Refresh();if(-not $child.HasExited){try{Assert-Child $child.Id $sxi;Stop-Process -Id $child.Id -Force -ErrorAction Stop}catch{Write-Error "emergency child cleanup failed: $($_.Exception.Message)"}}}
    if($script:associationChanged){
      Set-ItemProperty -LiteralPath $associationPath -Name ListOfAssociations -Value $associationOriginal
      $script:associationChanged=$false
    }
    $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o')
    Record-Step $step
  }
}
if(-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME){throw 'session-0 SSH required'}
if($RunId -ne 'k04-var04-duplicate-control-key-v100-ssh-20261004-01'){throw 'run id differs from frozen source'}
if(Test-Path -LiteralPath $run){throw 'immutable native run already exists'}
if(-not(Test-Path -LiteralPath $workingDirectory)){throw 'pinned working directory absent'}
$ancestors=@();$ancestorPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $ancestorPid -gt 0;$depth++){
  $ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if(-not $ancestor){break}
  $ancestors += $ancestor.Name;$ancestorPid=$ancestor.ParentProcessId
}
if($ancestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
Add-Content -LiteralPath (Join-Path $case 'preflight.trace') -Value 'ssh ancestry verified'
Write-Output 'K04.var04 preflight: SSH ancestry verified'
foreach($entry in $sources.GetEnumerator()){
  Write-Output "K04.var04 preflight: hash $($entry.Key)"
  $path,$expected=$entry.Value
  if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}
}
Write-Output 'K04.var04 preflight: literal hashes verified'
& $python (Join-Path $case 'build.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen builder failed'}
Write-Output 'K04.var04 preflight: frozen builder verified'
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'K04' -or $contract.variant_id -ne 'K04.var04' -or $contract.version -ne '1.0.0-candidate' -or
   $contract.run_id -ne $RunId -or $contract.dependency.closure_sha256 -ne $sources.accepted_parent_closure[1] -or
   $contract.dependency.signoff_sha256 -ne $sources.accepted_parent_signoff[1] -or
   $contract.inputs_sha256.control_main -ne $sources.control_main[1] -or
   $contract.inputs_sha256.key_main -ne $sources.key_main[1] -or
   $contract.inputs_sha256.control_mdb_source -ne $sources.control_mdb_source[1] -or
   $contract.inputs_sha256.key_level1_source -ne $sources.key_level1_source[1] -or
   $contract.inputs_sha256.key_level2_source -ne $sources.key_level2_source[1]){throw 'frozen contract fields differ'}
Write-Output 'K04.var04 preflight: contract verified'
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false;$runCreated=$false;$sealed=$false;$associationChanged=$false;$fatalError=$null;$steps=@()
try {
  try{$acquired=$queue.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
  if(-not $acquired){throw 'host-wide native queue busy'}
  $existing=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -le 0){throw 'expected protected GUI only'}
  $script:guiSession=$existing[0].SessionId;$script:guiStart=$existing[0].StartTime.ToUniversalTime().ToString('o')
  $sessions=@(qwinsta 2>&1)
  if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1){throw 'GUI session not active'}
  if((Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations) -cne $associationOriginal){throw 'MDB association differs'}
  New-Item -ItemType Directory -Path $run -ErrorAction Stop | Out-Null;$runCreated=$true
  foreach($name in @('control-main-input.json','key-main-input.json','control-mdb-source.json','key-level1-source.json','key-level2-source.json')){
    Copy-Item -LiteralPath (Join-Path $case $name) -Destination (Join-Path $run $name)
  }
  $sourceHashes=[ordered]@{}
  foreach($entry in $sources.GetEnumerator()){$sourceHashes[$entry.Key]=$entry.Value[1]}
  foreach($name in @('build.py','create_mdb_x86.ps1','run_native_ssh.ps1')){$sourceHashes[$name]=Hash (Join-Path $case $name)}
  $sourceHashes.python=Hash $python;$sourceHashes.powershell_x86=Hash $ps32
  [ordered]@{schema='simlox-k04-var04-conflict-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$workingDirectory;association_before=$associationOriginal;association_during_calc=$associationTemporary;source_hashes_before=$sourceHashes;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $errorText=$null;$outcomes=[ordered]@{}
  try {
    Write-Output 'K04.var04 native: create three MDB files'
    Run-Generator 'control' (Join-Path $run 'control-mdb-source.json') (Join-Path $run 'control.mdb')
    Run-Generator 'key_level2' (Join-Path $run 'key-level2-source.json') (Join-Path $run 'key-level2.mdb')
    Run-Generator 'key_level1' (Join-Path $run 'key-level1-source.json') (Join-Path $run 'key-level1.mdb')
    foreach($arm in @('control','key')){
      Write-Output "K04.var04 native: $arm import/export/calc"
      $sxi=Join-Path $run "$arm.sxi";$sxo=Join-Path $run "$arm.sxo"
      $input=Join-Path $run "$arm-main-input.json"
      Run-Simlox "${arm}_import" ('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $input,$sxi,(Join-Path $run "$arm-import.log")) $sxi $false
      Run-Simlox "${arm}_export" ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run "$arm-roundtrip-raw.json"),(Join-Path $run "$arm-export.log")) $sxi $false
      if((Get-Item -LiteralPath $sxi).Length -le 4 -or (Get-Item -LiteralPath (Join-Path $run "$arm-roundtrip-raw.json")).Length -le 4){throw "$arm SXI or roundtrip empty"}
      Run-Simlox "${arm}_calc" ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run "$arm-run.log")) $sxi $true
      $log=Get-Content -LiteralPath (Join-Path $run "$arm-run.log") -Raw -Encoding UTF8
      $errors=@([regex]::Matches($log,'\(error #(\d+)\)') | ForEach-Object {$_.Groups[1].Value})
      $warnings=@([regex]::Matches($log,'\(warning #(\d+)\)') | ForEach-Object {$_.Groups[1].Value})
      $outcomes[$arm]=[ordered]@{sxi_sha256=Hash $sxi;sxo_bytes=(Get-Item -LiteralPath $sxo).Length;run_log_sha256=Hash (Join-Path $run "$arm-run.log");converter_error_codes=$errors;converter_warning_codes=$warnings;converter_summary=([regex]::Match($log,'Input conversion completed\. Errors: \d+, Warnings: \d+, Notes: \d+').Value)}
      if((Get-Item -LiteralPath $sxo).Length -gt 4){
        Run-Simlox "${arm}_jsonreport" ('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,(Join-Path $run "$arm-report-raw.json"),(Join-Path $run "$arm-report-export.log")) $sxo $false
      }
    }
  } catch {$errorText=$_.Exception.Message}
  [ordered]@{schema='simlox-k04-var04-conflict-outcomes/v1';run_id=$RunId;arms=$outcomes;error=$errorText} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'outcomes.json') -Encoding UTF8
  $sourceHashesAfter=[ordered]@{}
  foreach($entry in $sources.GetEnumerator()){$sourceHashesAfter[$entry.Key]=Hash $entry.Value[0]}
  foreach($name in @('build.py','create_mdb_x86.ps1','run_native_ssh.ps1')){$sourceHashesAfter[$name]=Hash (Join-Path $case $name)}
  $sourceHashesAfter.python=Hash $python;$sourceHashesAfter.powershell_x86=Hash $ps32
  foreach($key in $sourceHashes.Keys){if($sourceHashes[$key] -ne $sourceHashesAfter[$key]){$errorText="source changed during run: $key"}}
  $raw=@{}
  foreach($file in Get-ChildItem -LiteralPath $run -File){if($file.Name -ne 'invocation.json'){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}}
  [ordered]@{schema='simlox-k04-var04-conflict-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$sourceHashes;source_hashes_after=$sourceHashesAfter;association_after=(Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations);raw=$raw;error=$errorText;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true
  if($errorText){throw $errorText}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;outcomes=$outcomes} | ConvertTo-Json -Depth 7)
} catch {$fatalError=$_.Exception.Message;throw}
finally {
  if($associationChanged){try{Set-ItemProperty -LiteralPath $associationPath -Name ListOfAssociations -Value $associationOriginal}catch{Write-Error "emergency MDB association restore failed: $($_.Exception.Message)"}}
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    $partial=@{}
    foreach($file in Get-ChildItem -LiteralPath $run -File){if($file.Name -ne 'invocation.json'){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}}
    [ordered]@{schema='simlox-k04-var04-conflict-closure/v1';run_id=$RunId;raw=$partial;error=$fatalError;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null}
  $queue.Dispose()
}

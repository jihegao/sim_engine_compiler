param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$run=Join-Path (Join-Path $case 'runs') $RunId
$parent=Join-Path (Split-Path $case -Parent) 'K02-var01-json-structure-v1.0.1'
$parentRun=Join-Path (Join-Path $parent 'runs') 'k02-var01-named-v101-ssh-20261004-01'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$ps32='C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$associationPath='HKCU:\Software\Systecon\SIMLOX Version 2017\Database Associations'
$associationOriginal='mdb=Microsoft Access Driver (*.mdb)|'
$dsnName='SIMLOX_I18_K05V02_101_20261004'
$dsnDriver='Microsoft Access Driver (*.mdb, *.accdb)'
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'f2f824a595951436f0f37b00c7cd70cd56f18fe7390f1b89f5a66261126ada78')
  baseline_input=@((Join-Path $case 'baseline-input.json'),'bd5c4d2106b3e39d80721e608c58980b37a0e696f685205cd14daf46e2099604')
  database_source=@((Join-Path $case 'database-source.json'),'64e2512173cbef214af97fc544cc80ef6a4506f8fb0d78596adf2070c41baa09')
  accepted_parent_input=@((Join-Path $parent 'named-input.json'),'b94e367d46665d4d58f2fb8d15771a61a6d51369070db85ab9bda851c3e76b00')
  accepted_parent_sxi=@((Join-Path $parentRun 'model.sxi'),'60c7a5cddd2af357282d948aa92409f526d751a173b19c931f9a5213f83e8815')
  accepted_parent_roundtrip=@((Join-Path $parentRun 'roundtrip-raw.json'),'7d3a6ebe5b9b1170dca1d8115555ebb26dc4c47c03cc325e4d6576bd921dc9e9')
  accepted_parent_closure=@((Join-Path $parentRun 'closure.json'),'86e93d3fc94dcae4b034432b2ccea16e84c7b3e17894d3e5ea6ef1bdb2b999c3')
  accepted_parent_signoff=@((Join-Path $parent 'cli-scope-signoff-2026-10-04.md'),'e4f14cbdb2e74237189a46d2a743101b4033a0f3d59c38619ca7eb208ca67e89')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual=@($manual,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
}
function Hash([string]$path){return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Assert-Gui {
  $p=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $script:guiSession -or
     $p[0].StartTime.ToUniversalTime().ToString('o') -ne $script:guiStart){throw 'protected GUI process changed'}
}
function Assert-Child([int]$childPid,[string]$needle){
  $w=Get-CimInstance Win32_Process -Filter "ProcessId=$childPid"
  $p=Get-Process -Id $childPid -ErrorAction Stop
  if(-not $w -or $w.Name -ne 'Simlox.exe' -or $p.SessionId -ne 0 -or
     -not $w.CommandLine.Contains($needle)){throw 'native child identity differs'}
}
function Record-Step($step){
  $script:steps += $step
  ConvertTo-Json -InputObject $script:steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
}
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
    if($child){$child.Refresh();if(-not $child.HasExited){try{Assert-Child $child.Id $needle;Stop-Process -Id $child.Id -Force -ErrorAction Stop}catch{Write-Error "emergency child cleanup failed: $($_.Exception.Message)"}}}
    $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o');Record-Step $step
  }
}
function Own-Dsn {
  $dsn=@(Get-OdbcDsn -Name $dsnName -DsnType User -Platform '64-bit' -ErrorAction SilentlyContinue)
  if($dsn.Count -eq 0){return $false}
  if($dsn.Count -ne 1 -or $dsn[0].DriverName -cne $dsnDriver -or
     $dsn[0].Attribute['DBQ'] -cne (Join-Path $run 'input.mdb')){throw 'temporary DSN identity differs'}
  return $true
}
function Remove-OwnedDsn {
  if(Own-Dsn){Remove-OdbcDsn -Name $dsnName -DsnType User -Platform '64-bit' -ErrorAction Stop}
  if(Get-OdbcDsn -Name $dsnName -DsnType User -Platform '64-bit' -ErrorAction SilentlyContinue){throw 'temporary DSN removal failed'}
}
if(-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME){throw 'session-0 SSH required'}
if($RunId -ne 'k05-var02-odbc-null-v101-ssh-20261004-01'){throw 'run ID differs from frozen contract'}
if(Test-Path -LiteralPath $run){throw 'immutable native run already exists'}
if(-not(Test-Path -LiteralPath $workingDirectory)){throw 'pinned working directory absent'}
$ancestors=@();$ancestorPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $ancestorPid -gt 0;$depth++){
  $ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if(-not $ancestor){break}
  $ancestors += $ancestor.Name;$ancestorPid=$ancestor.ParentProcessId
}
if($ancestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
foreach($entry in $sources.GetEnumerator()){
  $path,$expected=$entry.Value
  if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}
}
& $python (Join-Path $case 'build.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen builder failed'}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'K05' -or $contract.variant_id -ne 'K05.var02' -or
   $contract.version -ne '1.0.1-candidate' -or $contract.run_id -ne $RunId -or
   $contract.user_dsn -ne $dsnName -or $contract.inputs_sha256.baseline_input -ne $sources.baseline_input[1] -or
   $contract.inputs_sha256.database_source -ne $sources.database_source[1] -or
   $contract.dependency.native_sxi_sha256 -ne $sources.accepted_parent_sxi[1] -or
   $contract.dependency.closure_sha256 -ne $sources.accepted_parent_closure[1]){throw 'frozen contract fields differ'}
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false;$runCreated=$false;$sealed=$false;$dsnAttempted=$false;$steps=@();$fatalError=$null
try {
  try{$acquired=$queue.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
  if(-not $acquired){throw 'host-wide native queue busy'}
  $existing=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -le 0){throw 'expected protected GUI only'}
  $script:guiSession=$existing[0].SessionId;$script:guiStart=$existing[0].StartTime.ToUniversalTime().ToString('o')
  $sessions=@(qwinsta 2>&1)
  if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {$_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)')}).Count -ne 1){throw 'GUI session not active'}
  if((Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations) -cne $associationOriginal){throw 'MDB association differs'}
  if(Get-OdbcDsn -Name $dsnName -DsnType User -Platform '64-bit' -ErrorAction SilentlyContinue){throw 'task user DSN already exists'}
  New-Item -ItemType Directory -Path $run -ErrorAction Stop | Out-Null;$runCreated=$true
  Copy-Item -LiteralPath (Join-Path $case 'baseline-input.json') -Destination (Join-Path $run 'baseline-input.json')
  Copy-Item -LiteralPath (Join-Path $case 'database-source.json') -Destination (Join-Path $run 'database-source.json')
  $sourceHashes=[ordered]@{}
  foreach($entry in $sources.GetEnumerator()){$sourceHashes[$entry.Key]=$entry.Value[1]}
  foreach($name in @('build.py','create_mdb_x86.ps1','run_native_ssh.ps1')){$sourceHashes[$name]=Hash (Join-Path $case $name)}
  $sourceHashes.python=Hash $python;$sourceHashes.powershell_x86=Hash $ps32
  [ordered]@{schema='simlox-k05-var02-odbc-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$workingDirectory;association_before=$associationOriginal;dsn_before='absent';dsn_name=$dsnName;dsn_driver=$dsnDriver;source_hashes_before=$sourceHashes;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{baseline='not_started';import_export='not_started';calc='not_started';report='not_started';dsn_removed_before_calc=$false;error=$null}
  try {
    $base=Join-Path $run 'base.sxi';$baseSxo=Join-Path $run 'base.sxo'
    Write-Output 'K05.var02 native: default-Station baseline import/export/calc/report'
    Run-Simlox 'baseline_import' ('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'baseline-input.json'),$base,(Join-Path $run 'base-import.log')) (Join-Path $run 'base-import.log')
    if(-not(Test-Path -LiteralPath $base) -or (Get-Item -LiteralPath $base).Length -le 4){throw 'baseline SXI absent/empty'}
    Run-Simlox 'baseline_export' ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $base,(Join-Path $run 'base-roundtrip-raw.json'),(Join-Path $run 'base-export.log')) (Join-Path $run 'base-export.log')
    if(-not(Test-Path -LiteralPath (Join-Path $run 'base-roundtrip-raw.json')) -or (Get-Item -LiteralPath (Join-Path $run 'base-roundtrip-raw.json')).Length -le 1000){throw 'baseline export absent/empty'}
    Run-Simlox 'baseline_calc' ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $base,(Join-Path $run 'base-run.log')) (Join-Path $run 'base-run.log')
    $baseLog=Get-Content -LiteralPath (Join-Path $run 'base-run.log') -Raw -Encoding UTF8
    if($baseLog -notmatch 'Input conversion completed\. Errors: 0,' -or $baseLog -match '\(error #' -or
       -not(Test-Path -LiteralPath $baseSxo) -or (Get-Item -LiteralPath $baseSxo).Length -le 4){throw 'baseline converter rejection or unusable SXO'}
    Run-Simlox 'baseline_jsonreport' ('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $baseSxo,(Join-Path $run 'base-report-raw.json'),(Join-Path $run 'base-report-export.log')) (Join-Path $run 'base-report-export.log')
    if(-not(Test-Path -LiteralPath (Join-Path $run 'base-report-raw.json')) -or (Get-Item -LiteralPath (Join-Path $run 'base-report-raw.json')).Length -le 1000){throw 'baseline JSON report absent/empty'}
    $outcome.baseline='completed'
    Write-Output 'K05.var02 native: create and read back MDB'
    $gen=[ordered]@{name='database_create';started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;status='started';gui_preserved=$false;error=$null}
    try {
      Assert-Gui
      & $ps32 '-NoProfile' '-ExecutionPolicy' 'Bypass' '-File' (Join-Path $case 'create_mdb_x86.ps1') '-Source' (Join-Path $run 'database-source.json') '-Output' (Join-Path $run 'input.mdb')
      $gen.exit_code=$LASTEXITCODE
      Assert-Gui;$gen.gui_preserved=$true
      if($gen.exit_code -ne 0){throw "MDB generator exit=$($gen.exit_code)"}
      if((Get-Item -LiteralPath (Join-Path $run 'input.mdb')).Length -le 4 -or
         (Get-Item -LiteralPath (Join-Path $run 'input.readback.json')).Length -le 4){throw 'MDB/readback empty'}
      $gen.status='completed'
    } catch {$gen.status='failed';$gen.error=$_.Exception.Message;throw}
    finally {$gen.completed_utc=(Get-Date).ToUniversalTime().ToString('o');Record-Step $gen}
    Write-Output 'K05.var02 native: create task user DSN'
    $dsnAttempted=$true
    Add-OdbcDsn -Name $dsnName -DriverName $dsnDriver -DsnType User -Platform '64-bit' -SetPropertyValue @("DBQ=$(Join-Path $run 'input.mdb')") -ErrorAction Stop
    if(-not(Own-Dsn)){throw 'temporary DSN missing'}
    $odbc=[System.Data.Odbc.OdbcConnection]::new("DSN=$dsnName;ReadOnly=1;")
    try {
      $odbc.Open();$cmd=$odbc.CreateCommand();$cmd.CommandText='SELECT [STID],[DESCR],[QTY],[TYPE] FROM [Station]'
      $reader=$cmd.ExecuteReader()
      if(-not $reader.Read() -or $reader.GetString(0) -cne 'BASE-01' -or
         $reader.GetString(1) -cne 'ODBC merged teaching base' -or -not $reader.IsDBNull(2) -or
         -not $reader.IsDBNull(3) -or $reader.Read()){throw '64-bit DSN row differs'}
      $reader.Close()
    } finally {$odbc.Close()}
    [ordered]@{schema='simlox-k05-var02-dsn-observation/v1';name=$dsnName;driver=$dsnDriver;platform='64-bit';type='User';database_path=(Join-Path $run 'input.mdb');database_sha256=Hash (Join-Path $run 'input.mdb');select_row=@('BASE-01','ODBC merged teaching base',$null,$null)} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'dsn-observation.json') -Encoding UTF8
    $base=Join-Path $run 'base.sxi';$model=Join-Path $run 'model.sxi';$sxo=Join-Path $run 'model.sxo'
    Write-Output 'K05.var02 native: ODBC import into accepted SXI'
    Run-Simlox 'odbc_import' ('"{0}" -silent -import {1} -save "{2}" -log "{3}" -close' -f $base,$dsnName,$model,(Join-Path $run 'import.log')) (Join-Path $run 'import.log')
    if(-not(Test-Path -LiteralPath $model) -or (Get-Item -LiteralPath $model).Length -le 4){throw 'merged SXI absent/empty'}
    Remove-OwnedDsn
    $outcome.dsn_removed_before_calc=$true
    Write-Output 'K05.var02 native: merged SXI JSON export'
    Run-Simlox 'merged_export' ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $model,(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'export.log')) (Join-Path $run 'export.log')
    if(-not(Test-Path -LiteralPath (Join-Path $run 'roundtrip-raw.json')) -or
       (Get-Item -LiteralPath (Join-Path $run 'roundtrip-raw.json')).Length -le 1000){throw 'merged JSON export absent/empty'}
    $outcome.import_export='completed'
    Write-Output 'K05.var02 native: calculate merged SXI'
    Run-Simlox 'calc' ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $model,(Join-Path $run 'run.log')) (Join-Path $run 'run.log')
    $log=Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw -Encoding UTF8
    if($log -notmatch 'Input conversion completed\. Errors: 0,' -or $log -match '\(error #' -or
       -not(Test-Path -LiteralPath $sxo) -or (Get-Item -LiteralPath $sxo).Length -le 4){throw 'converter rejected merged model or SXO unusable'}
    $outcome.calc='completed'
    Write-Output 'K05.var02 native: JSON report'
    Run-Simlox 'jsonreport' ('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,(Join-Path $run 'report-raw.json'),(Join-Path $run 'report-export.log')) (Join-Path $run 'report-export.log')
    if(-not(Test-Path -LiteralPath (Join-Path $run 'report-raw.json')) -or
       (Get-Item -LiteralPath (Join-Path $run 'report-raw.json')).Length -le 1000){throw 'JSON report absent/empty'}
    $outcome.report='completed'
  } catch {$outcome.error=$_.Exception.Message}
  finally {if($dsnAttempted){Remove-OwnedDsn}}
  $outcome | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $sourceHashesAfter=[ordered]@{}
  foreach($entry in $sources.GetEnumerator()){$sourceHashesAfter[$entry.Key]=Hash $entry.Value[0]}
  foreach($name in @('build.py','create_mdb_x86.ps1','run_native_ssh.ps1')){$sourceHashesAfter[$name]=Hash (Join-Path $case $name)}
  $sourceHashesAfter.python=Hash $python;$sourceHashesAfter.powershell_x86=Hash $ps32
  foreach($key in $sourceHashes.Keys){if($sourceHashes[$key] -ne $sourceHashesAfter[$key]){$outcome.error="source changed during run: $key"}}
  $outcome | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{}
  foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-k05-var02-odbc-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$sourceHashes;source_hashes_after=$sourceHashesAfter;association_after=(Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations);dsn_after='absent';raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true
  if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatalError=$_.Exception.Message;throw}
finally {
  if($dsnAttempted){try{Remove-OwnedDsn}catch{Write-Error "emergency temporary DSN cleanup failed: $($_.Exception.Message)"}}
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try {
      $partial=[ordered]@{}
      foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
      [ordered]@{schema='simlox-k05-var02-odbc-closure/v1';run_id=$RunId;invocation_sha256=$(if(Test-Path -LiteralPath (Join-Path $run 'invocation.json')){Hash (Join-Path $run 'invocation.json')}else{$null});raw=$partial;error=$fatalError;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
    } catch {Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null}
  $queue.Dispose()
}

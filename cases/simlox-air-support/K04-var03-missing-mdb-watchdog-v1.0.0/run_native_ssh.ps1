param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$run=Join-Path (Join-Path $case 'runs') $RunId
$parent=Join-Path (Split-Path $case -Parent) 'K04-var02-relative-cwd-v1.0.4'
$parentRun=Join-Path (Join-Path $parent 'runs') 'k04-var02-relative-cwd-v104-ssh-20261004-01'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$associationPath='HKCU:\Software\Systecon\SIMLOX Version 2017\Database Associations'
$associationOriginal='mdb=Microsoft Access Driver (*.mdb)|'
$associationTemporary='mdb=Microsoft Access Driver (*.mdb, *.accdb)|'
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'815fcd34e9ef2d8c2f643ae5118786a2f584ad36b4d8757fe2e6163d62d51ebf')
  parent_sxi=@((Join-Path $parentRun 'model.sxi'),'7d0920e7b099d2f0eabb1dc2c69279de303cfec19c548405907aa07beab4e78a')
  parent_closure=@((Join-Path $parentRun 'closure.json'),'054a9944aa8263c1a77e11bd2eb0e2375947d7ec8e1e82d3e074402fca780664')
  parent_signoff=@((Join-Path $parent 'cli-scope-signoff-2026-10-04.md'),'a4ab04aab550d5911d6914acd736615c6ab4381d12e4c05e1846a786baad80d5')
  parent_main=@((Join-Path $parent 'main-input.json'),'986316de56ee3ceb4503137a2c788204a44a89fde3cf84d9c85cc562b2e05d7f')
  parent_event=@((Join-Path $parentRun 'positive-model.log'),'2d2e6c368305203052e347748dab8f36261947dae6f6a189fad4312e47c0a491')
  parent_report=@((Join-Path $parentRun 'positive-report-raw.json'),'5a3fd9007de442ce0f7a5210cd61cfe1e3a362774300497020341dc05d478655')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual=@($manual,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
}
function Hash([string]$path) { return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Assert-Gui {
  $p=@(Get-Process Simlox -ErrorAction SilentlyContinue | Where-Object {$_.Id -eq 13340})
  if ($p.Count -ne 1 -or $p[0].SessionId -ne $script:guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $script:guiStart) { throw 'protected GUI process changed' }
}
function Assert-Child([int]$childPid,[string]$sxi) {
  $w=Get-CimInstance Win32_Process -Filter "ProcessId=$childPid"
  $p=Get-Process -Id $childPid -ErrorAction Stop
  if (-not $w -or $w.Name -ne 'Simlox.exe' -or $p.SessionId -ne 0 -or -not $w.CommandLine.Contains($sxi)) { throw 'watchdog child identity differs' }
  return $w
}
function Snapshot([string]$label,[System.Diagnostics.Process]$proc,[string]$sxi) {
  $proc.Refresh()
  $alive=-not $proc.HasExited
  $w=if($alive){Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)"}else{$null}
  $p=if($alive){Get-Process -Id $proc.Id -ErrorAction SilentlyContinue}else{$null}
  $files=[ordered]@{}
  foreach($name in @('model.sxi','model.sxo','run.log','model.log')) {
    $path=Join-Path $run $name
    $files[$name]=if(Test-Path -LiteralPath $path){(Get-Item -LiteralPath $path).Length}else{$null}
  }
  return [ordered]@{
    label=$label; observed_utc=(Get-Date).ToUniversalTime().ToString('o')
    child_pid=$proc.Id; child_alive=$alive
    child_name=if($w){$w.Name}else{$null}
    child_session_id=if($p){$p.SessionId}else{$null}
    child_command_line=if($w){$w.CommandLine}else{$null}
    child_cpu_seconds=if($p){$p.CPU}else{$null}
    main_window_handle=if($p){[string]$p.MainWindowHandle}else{$null}
    main_window_title=if($p){$p.MainWindowTitle}else{$null}
    files=$files
  }
}
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if ($RunId -ne 'k04-var03-missing-mdb-v100-ssh-20261004-01') { throw 'run id differs from frozen contract' }
if (Test-Path -LiteralPath $run) { throw 'immutable native run already exists' }
$ancestors=@(); $ancestorPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $ancestorPid -gt 0;$depth++) {
  $ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if(-not $ancestor){break}
  $ancestors += $ancestor.Name; $ancestorPid=$ancestor.ParentProcessId
}
if($ancestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
foreach($entry in $sources.GetEnumerator()) {
  $path,$expected=$entry.Value
  if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}
}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'K04' -or $contract.variant_id -ne 'K04.var03' -or $contract.version -ne '1.0.0-candidate' -or $contract.run_id -ne $RunId -or
   $contract.dependency.sxi_sha256 -ne $sources.parent_sxi[1] -or $contract.dependency.closure_sha256 -ne $sources.parent_closure[1] -or
   $contract.dependency.signoff_sha256 -ne $sources.parent_signoff[1] -or $contract.watchdog_ms[0] -ne 20000 -or $contract.watchdog_ms[1] -ne 25000) { throw 'frozen contract fields differ' }
$parentClosure=Get-Content -LiteralPath (Join-Path $parentRun 'closure.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$parentLevel1=Join-Path $parentRun 'level1.mdb'
if($parentClosure.error -or (Hash $parentLevel1) -ne $parentClosure.raw.'level1.mdb'.sha256 -or -not(Test-Path -LiteralPath (Join-Path $parentRun 'level2.mdb'))) { throw 'accepted parent MDB prerequisite differs' }
$main=Get-Content -LiteralPath (Join-Path $parent 'main-input.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$include=@($main.model.tables | Where-Object {$_.name -eq 'IncludeFiles'})
if($include.Count -ne 1 -or $include[0].instances[0].rows[0][0] -cne 'level1.mdb') { throw 'accepted parent relative include differs' }
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false; $runCreated=$false; $sealed=$false; $associationChanged=$false; $child=$null; $fatalError=$null
try {
  try{$acquired=$queue.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
  if(-not $acquired){throw 'host-wide native queue busy'}
  $existing=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -le 0){throw 'expected protected GUI only'}
  $script:guiSession=$existing[0].SessionId
  $script:guiStart=$existing[0].StartTime.ToUniversalTime().ToString('o')
  $sessions=@(qwinsta 2>&1)
  if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1){throw 'GUI session not active'}
  if((Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations) -cne $associationOriginal){throw 'MDB association differs'}
  New-Item -ItemType Directory -Path $run -ErrorAction Stop | Out-Null; $runCreated=$true
  $sxi=Join-Path $run 'model.sxi'
  Copy-Item -LiteralPath $sources.parent_sxi[0] -Destination $sxi
  if((Hash $sxi) -ne $sources.parent_sxi[1] -or (Test-Path -LiteralPath (Join-Path $run 'level1.mdb'))){throw 'missing-file model setup differs'}
  $sourceHashes=[ordered]@{}
  foreach($entry in $sources.GetEnumerator()){$sourceHashes[$entry.Key]=$entry.Value[1]}
  $sourceHashes.runner=Hash (Join-Path $case 'run_native_ssh.ps1')
  $sourceHashes.parent_level1_mdb=Hash $parentLevel1
  $argumentLine='"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log')
  [ordered]@{schema='simlox-k04-var03-missing-mdb-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';model_sxi_sha256=Hash $sxi;model_directory=$run;working_directory=$parentRun;missing_file=(Join-Path $run 'level1.mdb');existing_working_directory_file=$parentLevel1;arguments=$argumentLine;watchdog_ms=@(20000,25000);association_before=$associationOriginal;association_during=$associationTemporary;source_hashes_before=$sourceHashes;publication_state='diagnostic_pending_review'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $observations=@(); $outcome=$null; $errorText=$null; $exitCode=$null; $childPid=$null
  try {
    Assert-Gui
    $associationChanged=$true
    Set-ItemProperty -LiteralPath $associationPath -Name ListOfAssociations -Value $associationTemporary
    if((Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations) -cne $associationTemporary){throw 'temporary MDB association did not apply'}
    $child=Start-Process -FilePath $exe -ArgumentList $argumentLine -WorkingDirectory $parentRun -WindowStyle Hidden -PassThru
    $childPid=$child.Id
    $null=Assert-Child $childPid $sxi
    $firstExited=$child.WaitForExit(20000)
    $observations += Snapshot 'after_20_seconds_or_exit' $child $sxi
    Assert-Gui
    if(-not $firstExited) {
      $secondExited=$child.WaitForExit(25000)
      $observations += Snapshot 'after_45_seconds_or_exit' $child $sxi
      Assert-Gui
      if(-not $secondExited) {
        $null=Assert-Child $childPid $sxi
        Stop-Process -Id $childPid -Force -ErrorAction Stop
        if(-not $child.WaitForExit(10000)){throw 'watchdog child did not exit after targeted stop'}
        $outcome='watchdog_terminated_after_45_seconds'
      }
    }
    if(-not $outcome){$outcome='native_exited_within_watchdog'}
    $child.Refresh(); $exitCode=$child.ExitCode
    Assert-Gui
  } catch { $errorText=$_.Exception.Message }
  finally {
    if($child) {
      $child.Refresh()
      if(-not $child.HasExited) {
        try { $null=Assert-Child $child.Id $sxi; Stop-Process -Id $child.Id -Force -ErrorAction Stop; $null=$child.WaitForExit(10000); $outcome='emergency_targeted_termination' }
        catch { $errorText="emergency child cleanup failed: $($_.Exception.Message)" }
      }
    }
    if($associationChanged) {
      Set-ItemProperty -LiteralPath $associationPath -Name ListOfAssociations -Value $associationOriginal
      $associationChanged=$false
    }
  }
  $finalSnapshot=if($child){Snapshot 'after_child_exit' $child $sxi}else{$null}
  [ordered]@{schema='simlox-k04-var03-missing-mdb-observation/v1';run_id=$RunId;outcome=$outcome;child_pid=$childPid;exit_code=$exitCode;timed_snapshots=$observations;final_snapshot=$finalSnapshot;watchdog_stopped_only_verified_child=($outcome -eq 'watchdog_terminated_after_45_seconds');gui_preserved=($null -eq $errorText);association_after=(Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations);error=$errorText} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'observation.json') -Encoding UTF8
  $sourceHashesAfter=[ordered]@{}
  foreach($entry in $sources.GetEnumerator()){$sourceHashesAfter[$entry.Key]=Hash $entry.Value[0]}
  $sourceHashesAfter.runner=Hash (Join-Path $case 'run_native_ssh.ps1')
  $sourceHashesAfter.parent_level1_mdb=Hash $parentLevel1
  foreach($key in $sourceHashes.Keys){if($sourceHashes[$key] -ne $sourceHashesAfter[$key]){$errorText="source changed during run: $key"}}
  $raw=@{}
  foreach($file in Get-ChildItem -LiteralPath $run -File){if($file.Name -ne 'invocation.json'){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}}
  [ordered]@{schema='simlox-k04-var03-missing-mdb-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$sourceHashes;source_hashes_after=$sourceHashesAfter;association_after=(Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations);raw=$raw;error=$errorText;outcome=$outcome;publication_state='diagnostic_pending_review'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true
  if($errorText){throw $errorText}
  Write-Output ([ordered]@{run_id=$RunId;outcome=$outcome;exit_code=$exitCode;run_dir=$run} | ConvertTo-Json)
} catch { $fatalError=$_.Exception.Message; throw }
finally {
  if($child) {
    $child.Refresh()
    if(-not $child.HasExited) {
      try { $null=Assert-Child $child.Id (Join-Path $run 'model.sxi'); Stop-Process -Id $child.Id -Force -ErrorAction Stop } catch { Write-Error "emergency child stop failed: $($_.Exception.Message)" }
    }
  }
  if($associationChanged) {
    try { Set-ItemProperty -LiteralPath $associationPath -Name ListOfAssociations -Value $associationOriginal }
    catch { Write-Error "emergency MDB association restore failed: $($_.Exception.Message)" }
  }
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))) {
    $partial=@{}
    foreach($file in Get-ChildItem -LiteralPath $run -File){if($file.Name -ne 'invocation.json'){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}}
    [ordered]@{schema='simlox-k04-var03-missing-mdb-closure/v1';run_id=$RunId;raw=$partial;error=$fatalError;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null}
  $queue.Dispose()
}

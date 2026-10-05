param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$run=Join-Path (Join-Path $case 'runs') $RunId
$root=Split-Path $case -Parent
$previous=Join-Path $root 'E14-var05-nfff-over-rrf-v1.0.0'
$previousRun=Join-Path (Join-Path $previous 'runs') 'e14-var05-nfff-over-rrf-v100-ssh-20261005-01'
$e14=Join-Path $root 'E14-var01-02-extra-removal-v1.0.0'
$e05=Join-Path $root 'E05-local-repair-reissue-v1.0.0'
$repo=Split-Path (Split-Path $root -Parent) -Parent
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'70acec30f0dfda35aeb205746415cc19f56355d17b8bcd2a7c1d781f6e74c396')
  index_verifier=@((Join-Path $case 'verify_parent_index.py'),'52c1a1bd9a8a14c2f000d6ff4f0709231be3632fdef7ed7b7ca06554e794fbc2')
  failed_contract=@((Join-Path $previous 'contract.json'),'8f515252cfa21a317b5d1b19d43467db28c84c8a22c29b3bd797ea2b5fb4f54e')
  failed_input=@((Join-Path $previousRun 'input.json'),'27e5d18f5b6bc4b88e3615c0cac229b9886ecfdb4ac5b543da30cb660a33c8a1')
  failed_closure=@((Join-Path $previousRun 'closure.json'),'2bc063c6dc8c1d318266ea55b1bcdc7147139cee35c9400d75414bf79a546ede')
  failed_sxi=@((Join-Path $previousRun 'model.sxi'),'223c381043341b331fddc16d058a9028a7bbc45ab6a0522e60d853beddc9c7c1')
  failed_import=@((Join-Path $previousRun 'import.log'),'7d90db4e5cc11ac7ad8f4a0d4642cb291bc215be196d164e7c48052cb4c2c0e5')
  failed_export=@((Join-Path $previousRun 'roundtrip-raw.json'),'f7a22fedc9d01e1042444517260e9646cc55a012dc71b99105d63f6afe97306b')
  e05_signoff=@((Join-Path $e05 'cli-scope-signoff-2026-09-29.md'),'e7f4e82be24e09d258345e5f8084ac99e822e8384cb5c8698fbd1ea687105f2f')
  e14_signoff=@((Join-Path $e14 'cli-scope-signoff-2026-10-05.md'),'03de3a793b4dce78c03243d949337988a83c42d137021c13ac0d1812e98b9d5e')
  e14_index=@((Join-Path $e14 'evidence-index.json'),'7f2318d933bc0281aac2b70c82d65fae0b97c6b4c08d5a7cb8b0cb6913f7d684')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual=@($manual,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
}
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Assert-Gui {
  $p=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne 1 -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne '2026-09-28T10:09:56.8261381Z'){throw 'protected GUI changed'}
}
function Assert-Child([int]$childPid,[string]$needle){
  $w=Get-CimInstance Win32_Process -Filter "ProcessId=$childPid";$p=Get-Process -Id $childPid -ErrorAction Stop
  if(-not $w -or $w.Name -ne 'Simlox.exe' -or $p.SessionId -ne 0 -or -not $w.CommandLine.Contains($needle)){throw 'native child identity differs'}
}
if(-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME){throw 'session-0 SSH required'}
if($RunId -ne 'e14-var05-nfff-over-rrf-v101-calc-ssh-20261005-01'){throw 'run ID differs from contract'}
if(Test-Path -LiteralPath $run){throw 'immutable run directory already exists'}
if(-not(Test-Path -LiteralPath $work)){throw 'pinned working directory absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $ancestor){break};$ancestors += $ancestor.Name;$parentPid=$ancestor.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.variant_id -ne 'E14.var05' -or $contract.version -ne '1.0.1-candidate' -or $contract.run_id -ne $RunId -or $contract.frozen_failed_import_arm.sxi_sha256 -ne $sources.failed_sxi[1] -or $contract.frozen_failed_import_arm.closure_sha256 -ne $sources.failed_closure[1] -or $contract.accepted_prerequisite.e14_index_local_crlf_sha256 -ne $sources.e14_index[1]){throw 'frozen contract fields differ'}
$commit='94a6dcdf6d175e98a00ffdf9c0fdc2a0102cd962';$published='9e12915cdc2679f04d84cab7113311b761396df5f86e937b3ea6f84037272942'
if($contract.accepted_prerequisite.e14_index_git_commit -ne $commit -or $contract.accepted_prerequisite.e14_index_git_lf_sha256 -ne $published){throw 'published index contract differs'}
& $python $sources.index_verifier[0] $repo "${commit}:cases/simlox-air-support/E14-var01-02-extra-removal-v1.0.0/evidence-index.json" $sources.e14_index[0] $sources.e14_index[1] 33683 $published 32883 | Out-Null
if($LASTEXITCODE -ne 0){throw 'published E14 index bytes differ'}
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false;$created=$false;$sealed=$false;$fatal=$null;$steps=@()
try {
  try{$acquired=$queue.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
  if(-not $acquired){throw 'host-wide native queue busy'}
  Assert-Gui
  $sessions=@(qwinsta 2>&1)
  if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {$_ -match '^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+1\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)'}).Count -ne 1){throw 'GUI session not active'}
  New-Item -ItemType Directory -Path $run -ErrorAction Stop | Out-Null;$created=$true
  Copy-Item -LiteralPath $sources.failed_sxi[0] -Destination (Join-Path $run 'model.sxi')
  $copiedSxi=Join-Path $run 'model.sxi'
  $copiedSxiBefore=Hash $copiedSxi
  if($copiedSxiBefore -ne $sources.failed_sxi[1] -or (Get-Item -LiteralPath $copiedSxi).Length -ne 190789){throw 'copied sealed SXI differs'}
  $before=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$before[$entry.Key]=$entry.Value[1]};$before.runner=Hash $PSCommandPath;$before.python=Hash $python
  [ordered]@{schema='simlox-e14-var05-calc-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');source_run_id=$contract.frozen_failed_import_arm.run_id;run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=1;start_utc='2026-09-28T10:09:56.8261381Z'};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$work;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{converter_summary=$null;error_codes=@();diagnostic_lines=@();copied_sxi_sha256_before=$copiedSxiBefore;copied_sxi_sha256_after=$null;copied_sxi_bytes_after=$null;expected_negative=$false;error=$null}
  $child=$null;$step=[ordered]@{name='calc_converter_gate';started_utc=(Get-Date).ToUniversalTime().ToString('o');exit_code=$null;status='started';gui_preserved=$false;error=$null}
  try {
    Assert-Gui
    $sxi=Join-Path $run 'model.sxi';$logPath=Join-Path $run 'run.log'
    $args='"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,$logPath
    $child=Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $work -WindowStyle Hidden -PassThru
    if(-not $child.WaitForExit(60000)){Assert-Child $child.Id $logPath;Stop-Process -Id $child.Id -Force -ErrorAction Stop;$null=$child.WaitForExit(10000);throw 'calc watchdog timeout after 60 seconds'}
    $step.exit_code=$child.ExitCode;Assert-Gui;$step.gui_preserved=$true
    if($step.exit_code -ne 0){throw "calc exit=$($step.exit_code)"}
    $step.status='completed'
  } catch {$step.status='failed';$step.error=$_.Exception.Message;$outcome.error=$step.error}
  finally {
    if($child){$child.Refresh();if(-not $child.HasExited){try{Assert-Child $child.Id $logPath;Stop-Process -Id $child.Id -Force -ErrorAction Stop}catch{Write-Error "targeted child cleanup failed: $($_.Exception.Message)"}}}
    $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o');$steps += $step
    ConvertTo-Json -InputObject $steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
  }
  if(-not $outcome.error){
    try {
      if(-not(Test-Path -LiteralPath $logPath) -or (Get-Item -LiteralPath $logPath).Length -le 4){throw 'calc log missing or too small'}
      $log=Get-Content -LiteralPath $logPath -Raw -Encoding UTF8
      $m=[regex]::Match($log,'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
      if(-not $m.Success){throw 'converter summary absent'}
      $outcome.converter_summary=@([int]$m.Groups[1].Value,[int]$m.Groups[2].Value,[int]$m.Groups[3].Value)
      $outcome.error_codes=@([regex]::Matches($log,'\(error #(\d+)\)') | ForEach-Object {$_.Groups[1].Value})
      $outcome.diagnostic_lines=@($log -split "`r?`n" | Where-Object {$_ -match '\(error #\d+\)'})
      if($outcome.converter_summary[0] -ne 1 -or $outcome.error_codes.Count -ne 1 -or $outcome.diagnostic_lines.Count -ne 1){throw 'sole target converter error absent or accompanied by another error'}
      $target=[regex]::Match($log,'(?mi)^Form:\s*ItemStructure\s*\r?\nrec\s+2:\s*\(error #\d+\)[^\r\n]*')
      if(-not $target.Success -or $target.Value -notmatch 'NFFF' -or $target.Value -notmatch '(?:TEACH-SRU-01|\b5(?:\.0+)?\b)'){throw 'error does not identify ItemStructure rec2 NFFF5 or target item'}
      $sxo=Join-Path $run 'model.sxo';if((Test-Path -LiteralPath $sxo) -and (Get-Item -LiteralPath $sxo).Length -gt 4){throw 'unexpected valid SXO'}
      foreach($name in @('model.log','selected-report-raw.json')){if(Test-Path -LiteralPath (Join-Path $run $name)){throw "unexpected event/report: $name"}}
      $outcome.expected_negative=$true
    } catch {$outcome.error=$_.Exception.Message}
  }
  $after=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$after[$entry.Key]=Hash $entry.Value[0]};$after.runner=Hash $PSCommandPath;$after.python=Hash $python
  foreach($key in $before.Keys){if($before[$key] -ne $after[$key]){$outcome.error="source changed during run: $key";$outcome.expected_negative=$false}}
  if(Test-Path -LiteralPath $copiedSxi){$outcome.copied_sxi_sha256_after=Hash $copiedSxi;$outcome.copied_sxi_bytes_after=(Get-Item -LiteralPath $copiedSxi).Length}
  if($outcome.copied_sxi_sha256_after -ne $sources.failed_sxi[1] -or $outcome.copied_sxi_bytes_after -ne 190789){$outcome.error='copied SXI changed during calculation';$outcome.expected_negative=$false}
  $outcome | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-e14-var05-calc-negative-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;expected_negative=$outcome.expected_negative;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true;if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;steps=$steps.Count;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($created -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$partial=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-e14-var05-calc-negative-closure/v1';run_id=$RunId;raw=$partial;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

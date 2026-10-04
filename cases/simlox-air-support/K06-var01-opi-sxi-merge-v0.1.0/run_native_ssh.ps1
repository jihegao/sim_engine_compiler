param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$run=Join-Path (Join-Path $case 'runs') $RunId
$source=Join-Path (Split-Path $case -Parent) 'K02-var01-json-structure-v1.0.1'
$sourceRun=Join-Path (Join-Path $source 'runs') 'k02-var01-named-v101-ssh-20261004-01'
$target=Join-Path (Split-Path $case -Parent) 'K01-var04-parent-child-model-diff-v1.0.0'
$targetRun=Join-Path (Join-Path $target 'runs') 'k01-var04-duration-v100-ssh-20261004-01'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'372d57636fbd7f13f31d7162a1dbecacab1ae6d2e3c2c50a0a5e5d404d80df99')
  source_input=@((Join-Path $source 'named-input.json'),'b94e367d46665d4d58f2fb8d15771a61a6d51369070db85ab9bda851c3e76b00')
  source_signoff=@((Join-Path $source 'cli-scope-signoff-2026-10-04.md'),'e4f14cbdb2e74237189a46d2a743101b4033a0f3d59c38619ca7eb208ca67e89')
  source_closure=@((Join-Path $sourceRun 'closure.json'),'86e93d3fc94dcae4b034432b2ccea16e84c7b3e17894d3e5ea6ef1bdb2b999c3')
  source_sxi=@((Join-Path $sourceRun 'model.sxi'),'60c7a5cddd2af357282d948aa92409f526d751a173b19c931f9a5213f83e8815')
  target_closure=@((Join-Path $targetRun 'closure.json'),'5200cc3f73c3dfce1b89f61314a0d98e460c4a9a08888139da0e3f8e3baa2b10')
  target_sxi=@((Join-Path $targetRun 'model.sxi'),'eedc015f9cd53c94036803656b0c84c83ddadcd92299397e769f4489482116c6')
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
if($RunId -ne 'k06-var01-opi-sxi-merge-v010-ssh-20261005-01'){throw 'run ID differs from contract'}
if(Test-Path -LiteralPath $run){throw 'immutable run directory already exists'}
if(-not(Test-Path -LiteralPath $work)){throw 'pinned working directory absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $ancestor){break};$ancestors += $ancestor.Name;$parentPid=$ancestor.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$sourceClosure=Get-Content -LiteralPath (Join-Path $sourceRun 'closure.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$targetClosure=Get-Content -LiteralPath (Join-Path $targetRun 'closure.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'K06' -or $contract.variant_id -ne 'K06.var01' -or $contract.version -ne '0.1.0-diagnostic' -or $contract.run_id -ne $RunId -or
  $contract.source.input_sha256 -ne $sources.source_input[1] -or $contract.source.signoff_sha256 -ne $sources.source_signoff[1] -or
  $contract.source.closure_sha256 -ne $sources.source_closure[1] -or $contract.source.native_sxi_sha256 -ne $sources.source_sxi[1] -or
  $contract.target.closure_sha256 -ne $sources.target_closure[1] -or $contract.target.native_sxi_sha256 -ne $sources.target_sxi[1] -or
  $contract.manual.sha256 -ne $sources.manual[1] -or $sourceClosure.error -or $targetClosure.error -or
  $sourceClosure.run_id -ne $contract.source.run_id -or $targetClosure.run_id -ne $contract.target.run_id -or
  $sourceClosure.raw.'model.sxi'.sha256 -ne $sources.source_sxi[1] -or $targetClosure.raw.'model.sxi'.sha256 -ne $sources.target_sxi[1]){throw 'frozen contract or accepted closures differ'}
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
  $opi=Join-Path $run 'source.opi';Copy-Item -LiteralPath $sources.source_sxi[0] -Destination $opi -ErrorAction Stop
  $base=Join-Path $run 'target.sxi';Copy-Item -LiteralPath $sources.target_sxi[0] -Destination $base -ErrorAction Stop
  if((Hash $opi) -ne $sources.source_sxi[1] -or (Get-Item -LiteralPath $opi).Length -ne 189410 -or
    (Hash $base) -ne $sources.target_sxi[1] -or (Get-Item -LiteralPath $base).Length -ne 189251){throw 'copied input differs from accepted native model'}
  $before=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$before[$entry.Key]=$entry.Value[1]}
  $before.runner=Hash $PSCommandPath
  [ordered]@{schema='simlox-k06-opi-sxi-merge-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$work;source_hashes_before=$before;copied_opi_sha256=(Hash $opi);copied_target_sha256=(Hash $base);publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{steps='not_started';converter_summary=$null;warning_codes=@();error=$null}
  try {
    $merged=Join-Path $run 'merged.sxi'
    Run-Simlox 'opi_sxi_import' ('"{0}" -silent -import "{1}" -save "{2}" -log "{3}" -close' -f $base,$opi,$merged,(Join-Path $run 'import.log')) (Join-Path $run 'import.log')
    Require-Size 'merged.sxi' 1000;Require-Size 'import.log' 4
    $importLog=Get-Content -LiteralPath (Join-Path $run 'import.log') -Raw -Encoding UTF8
    if([regex]::IsMatch($importLog,'(?im)(?:\berrors:\s*[1-9]|\(error #|\bfailed\b)')){throw 'import diagnostic contains error or failure'}
    Run-Simlox 'merged_json_export' ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $merged,(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'export.log')) (Join-Path $run 'export.log')
    Require-Size 'roundtrip-raw.json' 1000
    Run-Simlox 'merged_calc' ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $merged,(Join-Path $run 'run.log')) (Join-Path $run 'run.log')
    Require-Size 'run.log' 4;Require-Size 'merged.sxo' 1000;Require-Size 'merged.log' 4
    $log=Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw -Encoding UTF8
    $m=[regex]::Match($log,'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
    if(-not $m.Success){throw 'converter summary absent'}
    $outcome.converter_summary=@([int]$m.Groups[1].Value,[int]$m.Groups[2].Value,[int]$m.Groups[3].Value)
    $warningCodes=@([regex]::Matches($log,'\(warning #(\d+)\)') | ForEach-Object {$_.Groups[1].Value})
    $outcome.warning_codes=$warningCodes
    if([int]$m.Groups[1].Value -ne 0 -or [int]$m.Groups[3].Value -ne 0 -or @($warningCodes | Where-Object {$_ -notin @('108','126')}).Count -gt 0){throw 'unreviewed converter diagnostic'}
    $sxo=Join-Path $run 'merged.sxo'
    Run-Simlox 'merged_report' ('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,(Join-Path $run 'report-raw.json'),(Join-Path $run 'report-export.log')) (Join-Path $run 'report-export.log')
    Require-Size 'report-raw.json' 1000
    $outcome.steps='completed'
  } catch {$outcome.error=$_.Exception.Message}
  $after=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$after[$entry.Key]=Hash $entry.Value[0]};$after.runner=Hash $PSCommandPath
  foreach($key in $before.Keys){if($before[$key] -ne $after[$key]){$outcome.error="source changed during run: $key"}}
  $outcome | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-k06-opi-sxi-merge-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true;if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;steps=$steps.Count;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$partial=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-k06-opi-sxi-merge-closure/v1';run_id=$RunId;raw=$partial;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

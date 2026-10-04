param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$root=Split-Path $case -Parent
$run=Join-Path (Join-Path $case 'runs') $RunId
$parent=Join-Path $root 'D14-var01-monitored-item-pm-v1.0.1'
$d03=Join-Path $root 'D03-calendar-pm-v1.0.0'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'6b370a11ad8652075217d81246946e7588dd0f2c783fe4a65ca8a412a2ee6679')
  certain=@((Join-Path $case 'certain-input.json'),'4c047fad6e2a36463729959d4334c5107e1f62bbad0a055af51738dc28af5119')
  fractional=@((Join-Path $case 'fractional-input.json'),'ed0b027ed5b738e119ba4cb48c82a55926f0beca5e0e787952b7d7c3d0fd8632')
  report_builder=@((Join-Path $case 'make_report_settings.py'),'a64333fb80871a06a6e4bc08e564251d9adb5c64958ef5287a278b1fbb371f17')
  report_default=@('C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs','1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d')
  base01_selector=@((Join-Path $case 'runs\report-settings\base-01.sxs'),'10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b')
  parent_input=@((Join-Path $parent 'native-input-monitored.json'),'29dd9638ecaf5980b7ecf90ef41644afbbcca3a9b15f88dceb8f2fe3e5c32903')
  parent_closure=@((Join-Path $parent 'runs\d14-var01-monitored-v101-ssh-20261002-01\closure.json'),'7a0977eefefb06be79860ad0982efa2f8c0d4259c8b0905e2a17a5fca9122ead')
  parent_signoff=@((Join-Path $parent 'cli-scope-signoff-2026-10-02.md'),'848bb2d59d6fc918e73b7a1e551e1e427d40ad6d38a35569321835fbaed807f0')
  d03_signoff=@((Join-Path $d03 'cli-scope-signoff-2026-09-30.md'),'8c609dc19b1a4b7f027da9538096c5171244609b80cab9026e1ad360cd9006d1')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual=@($manual,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
}
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Assert-Gui {
  $p=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $script:guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $script:guiStart){throw 'protected GUI changed'}
}
function Assert-Child([int]$childPid,[string]$needle){
  $w=Get-CimInstance Win32_Process -Filter "ProcessId=$childPid"; $p=Get-Process -Id $childPid -ErrorAction Stop
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
if($RunId -ne 'd15-var01-pmrf-v100-ssh-20261004-01'){throw 'run ID differs from contract'}
if(Test-Path -LiteralPath $run){throw 'immutable run directory already exists'}
if(-not(Test-Path -LiteralPath $work)){throw 'pinned working directory absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $ancestor){break};$ancestors += $ancestor.Name;$parentPid=$ancestor.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
& $python (Join-Path $case 'make_report_settings.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen report selector verification failed'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
& $python (Join-Path $case 'build.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen builder verification failed'}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'D15' -or $contract.variant_id -ne 'D15.var01' -or $contract.run_id -ne $RunId -or $contract.inputs_sha256.certain -ne $sources.certain[1] -or $contract.inputs_sha256.fractional -ne $sources.fractional[1] -or $contract.dependency.geometry_input_sha256 -ne $sources.parent_input[1] -or $contract.dependency.geometry_closure_sha256 -ne $sources.parent_closure[1] -or $contract.dependency.geometry_signoff_sha256 -ne $sources.parent_signoff[1] -or $contract.dependency.catalog_parent_signoff_sha256 -ne $sources.d03_signoff[1] -or $contract.report_settings.installed_default_sha256 -ne $sources.report_default[1] -or $contract.report_settings.base01_selector_sha256 -ne $sources.base01_selector[1] -or $contract.manual.sha256 -ne $sources.manual[1]){throw 'frozen contract fields differ'}
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
  foreach($arm in @('certain','fractional')){Copy-Item -LiteralPath (Join-Path $case "$arm-input.json") -Destination (Join-Path $run "$arm-input.json")}
  $sourceHashes=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$sourceHashes[$entry.Key]=$entry.Value[1]}
  foreach($name in @('build.py','run_native_ssh.ps1')){$sourceHashes[$name]=Hash (Join-Path $case $name)};$sourceHashes.python=Hash $python
  [ordered]@{schema='simlox-d15-pmrf-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$work;source_hashes_before=$sourceHashes;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{certain='not_started';fractional='not_started';converter_summaries=[ordered]@{};warning_codes=[ordered]@{};error=$null}
  try {
    foreach($arm in @('certain','fractional')){
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
      $outcome[$arm]='completed'
    }
  } catch {$outcome.error=$_.Exception.Message}
  $after=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$after[$entry.Key]=Hash $entry.Value[0]};foreach($name in @('build.py','run_native_ssh.ps1')){$after[$name]=Hash (Join-Path $case $name)};$after.python=Hash $python
  foreach($key in $sourceHashes.Keys){if($sourceHashes[$key] -ne $after[$key]){$outcome.error="source changed during run: $key"}}
  $outcome | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-d15-pmrf-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$sourceHashes;source_hashes_after=$after;raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true;if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$partial=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-d15-pmrf-closure/v1';run_id=$RunId;raw=$partial;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

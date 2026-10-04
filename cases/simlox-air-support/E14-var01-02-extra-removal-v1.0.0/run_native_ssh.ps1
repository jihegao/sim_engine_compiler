param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$run=Join-Path (Join-Path $case 'runs') $RunId
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$default='C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$parent=Join-Path (Split-Path $case -Parent) 'G01-var01-lru-sru-v1.0.1'
$arms=@('seed2-control','seed2-extra','seed3-control','seed3-extra','seed4-control','seed4-extra','seed5-control','seed5-extra','seed6-control','seed6-extra')
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'609e94a618e149becc356cf6521d7b7b00c4a2d0ba86e09a23935983a7407650')
  builder=@((Join-Path $case 'build.py'),'62a730c8e438f9e4f5412a304fdeecb135efbedb4162a9e09d38c75bf3a51b7d')
  selector_builder=@((Join-Path $case 'make_report_settings.py'),'0fa06a3b35bfc39b3b48a4c66519a4929275d5d7e97dc18afaca29647bb8032a')
  parent_input=@((Join-Path $parent 'native-input.json'),'9c25a414615ac4ea523ee989385a913c692923e04bc41c6984b6866e86204bb9')
  parent_signoff=@((Join-Path $parent 'cli-scope-signoff-2026-10-01.md'),'6c35ae528908500d175c2db27568dfe470a947904d25f0b24494000f394a96a1')
  'seed2-control'=@((Join-Path $case 'seed2-control-input.json'),'e8b006f20c3b7567c435afa9a4cba2e1df473bd6e74835850af9a0e5092e09ac')
  'seed2-extra'=@((Join-Path $case 'seed2-extra-input.json'),'531a1f99e45b71ad0137aaf18650e3df84cec77a677beadaad7d35e4fdb84a75')
  'seed3-control'=@((Join-Path $case 'seed3-control-input.json'),'6c9a731d8fc55a1582e6a19da178988cac0c5bc3648f05b251be6b0c284468ee')
  'seed3-extra'=@((Join-Path $case 'seed3-extra-input.json'),'2e3677b3e3856d84f1192de600e200328c3de74063b98f4febcabf8ef1d05aae')
  'seed4-control'=@((Join-Path $case 'seed4-control-input.json'),'62e8f2f97c3114152009cbc64f2a777b98ca02f54c654b87d39526d0095ed78e')
  'seed4-extra'=@((Join-Path $case 'seed4-extra-input.json'),'5e77f07bd98d3ad168194e49237f338d2790685a7a95be5490f98b52be380a2d')
  'seed5-control'=@((Join-Path $case 'seed5-control-input.json'),'f9c52066492ed66abe4fe46178214503f701bb496721f34a9c972446f78af24a')
  'seed5-extra'=@((Join-Path $case 'seed5-extra-input.json'),'28e73607f3daf6bc7999cc03c1a87420bc9fd94289cbd9608e38b8bb930fe872')
  'seed6-control'=@((Join-Path $case 'seed6-control-input.json'),'5cc9ef653b9eab8aad3bf437e0106c907ea6c061b6d085bd9cdefbec676c3d4e')
  'seed6-extra'=@((Join-Path $case 'seed6-extra-input.json'),'7206c70beeb311bf4cc489c54cabdf652875bc8bb4e1ae98af811c1c322144a0')
  default=@($default,'1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d')
  selector_lru=@((Join-Path $case 'runs\report-settings\teach-lru-01.sxs'),'10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b')
  selector_sru01=@((Join-Path $case 'runs\report-settings\teach-sru-01.sxs'),'2463703548adbbcf46199c3e8f08ea8e5a96a84875e04648475e87fdefb612ad')
  selector_sru02=@((Join-Path $case 'runs\report-settings\teach-sru-02.sxs'),'f6f320fe334bd7edb5b0c5b22cb672245f977b600ee3632f6757d9f569d16b8b')
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
if($RunId -ne 'e14-var01-02-two-sru-panel-v100-ssh-20261005-01'){throw 'run ID differs from contract'}
if(Test-Path -LiteralPath $run){throw 'immutable run directory already exists'}
if(-not(Test-Path -LiteralPath $work)){throw 'pinned working directory absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $ancestor){break};$ancestors += $ancestor.Name;$parentPid=$ancestor.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
& $python (Join-Path $case 'make_report_settings.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen report selector verification failed'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
& $python (Join-Path $case 'build.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen input builder verification failed'}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'E14' -or $contract.version -ne '1.0.0-candidate' -or $contract.run_id -ne $RunId -or $contract.dependency.parent_input_sha256 -ne $sources.parent_input[1] -or $contract.dependency.parent_signoff_sha256 -ne $sources.parent_signoff[1] -or $contract.manual.sha256 -ne $sources.manual[1] -or $contract.report_settings.installed_default_sha256 -ne $sources.default[1]){throw 'frozen contract fields differ'}
foreach($arm in $arms){if($contract.inputs_sha256.$arm -ne $sources[$arm][1]){throw "contract input pin differs: $arm"}}
foreach($item in @(@('TEACH-LRU-01','selector_lru'),@('TEACH-SRU-01','selector_sru01'),@('TEACH-SRU-02','selector_sru02'))){if($contract.report_settings.item_selector_sha256.($item[0]) -ne $sources[$item[1]][1]){throw "selector pin differs: $($item[0])"}}
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
  [ordered]@{schema='simlox-e14-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$work;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
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
  [ordered]@{schema='simlox-e14-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true;if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;steps=$steps.Count;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$partial=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-e14-closure/v1';run_id=$RunId;raw=$partial;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

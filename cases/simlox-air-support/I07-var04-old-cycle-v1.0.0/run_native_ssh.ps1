param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$root=Split-Path $case -Parent
$parent=Join-Path $root 'E15-var01-time-based-cycle-v1.0.1'
$parentSource=Join-Path $root 'E15-var01-time-based-cycle-v1.0.0'
$parentRun=Join-Path (Join-Path $parentSource 'runs') 'e15-var01-timecycle-v100-ssh-20261005-01'
$parentReport=Join-Path (Join-Path $parent 'runs') 'e15-var01-timecycle-report-v101-ssh-20261005-01'
$selectorParent=Join-Path $root 'E15-var07-explicit-istoh-v1.0.1'
$selector=Join-Path (Join-Path $selectorParent 'runs') 'report-settings\item-position-results.sxs'
$selectorBuilder=Join-Path $selectorParent 'make_report_settings.py'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run=Join-Path (Join-Path $case 'runs') $RunId
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'dcb86a3309d90020f8dd1f846459d918a1391677e3e9c3ecfa4bfac247be5436')
  input=@((Join-Path $case 'native-input.json'),'6ee3b921af12f0455970dd62152c6b54e46a1112eb890ddfc9b10a4520c31505')
  builder=@((Join-Path $case 'build.py'),'69c889a984d74cfd34a9941bfbae462021fcf12287464ba6ad7b2b83878789c5')
  roundtrip_checker=@((Join-Path $case 'check_roundtrip.py'),'ffe80ff3aabec6c62c001c8045255b889f6ffa6a0280d4d6da266aab73d7261b')
  parent_input=@((Join-Path $parentSource 'native-input.json'),'d37bdc10592dff04e521d66276b49f9404dfea0511fac5ea73ef201b02b22b1f')
  parent_signoff=@((Join-Path $parent 'cli-scope-signoff-2026-10-05.md'),'b875964c50598dda9b65dbebb66d9339fa560cf5846b8abc3c345014adbdaa52')
  parent_index=@((Join-Path $parent 'evidence-index.json'),'b29bd16a3ebf1d4bdde6d1a5c743dddda8da82a785d777fdd399a403d8ee5af5')
  parent_event=@((Join-Path $parentRun 'model.log'),'d37165d77f783427b0311c983c3a47f32d3bc7cfc75518063036c03d6c436349')
  parent_report=@((Join-Path $parentReport 'selected-report-raw.json'),'d41c5d0a17e0456453f24bd2c142c2c2c84095ec7e65e7a7e5fdaffdc373c1e0')
  selector=@($selector,'841a6a077741566cac02b84e0cb35f4154f13a857e5665909a483cd6c051316c')
  selector_builder=@($selectorBuilder,'d2ede31eba96985da2e6671ef0f81fe0d010f5e2d6889f09531519e11c73df1e')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual=@($manual,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
}
function Assert-Gui {$p=@(Get-Process Simlox -ErrorAction SilentlyContinue);if($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne 1 -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne '2026-09-28T10:09:56.8261381Z'){throw 'protected GUI changed'}}
function Assert-Child([int]$childPid,[string]$needle){$w=Get-CimInstance Win32_Process -Filter "ProcessId=$childPid";$p=Get-Process -Id $childPid -ErrorAction Stop;if(-not $w -or $w.Name -ne 'Simlox.exe' -or $p.SessionId -ne 0 -or -not $w.CommandLine.Contains($needle)){throw 'native child identity differs'}}
function Save-Steps {ConvertTo-Json -InputObject $script:steps -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8}
function Run-Simlox([string]$name,[string]$argumentLine,[string]$needle){
  $step=[ordered]@{name=$name;arguments=$argumentLine;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;status='started';gui_preserved=$false;error=$null};$child=$null
  try {
    Assert-Gui
    $child=Start-Process -FilePath $exe -ArgumentList $argumentLine -WorkingDirectory $work -WindowStyle Hidden -PassThru
    if(-not $child.WaitForExit(60000)){Assert-Child $child.Id $needle;Stop-Process -Id $child.Id -Force -ErrorAction Stop;$null=$child.WaitForExit(10000);throw "$name watchdog timeout after 60 seconds"}
    $step.exit_code=$child.ExitCode;Assert-Gui;$step.gui_preserved=$true
    if($child.ExitCode -ne 0){throw "$name exit=$($child.ExitCode)"}
    $step.status='completed'
  } catch {$step.status='failed';$step.error=$_.Exception.Message;throw}
  finally {
    if($child){$child.Refresh();if(-not $child.HasExited){try{Assert-Child $child.Id $needle;Stop-Process -Id $child.Id -Force -ErrorAction Stop}catch{Write-Error "targeted child cleanup failed: $($_.Exception.Message)"}}}
    $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o');$script:steps += $step;Save-Steps
  }
}
function Require-Size([string]$name,[int64]$min){$p=Join-Path $run $name;if(-not(Test-Path -LiteralPath $p) -or (Get-Item -LiteralPath $p).Length -le $min){throw "$name missing or too small"}}
if(-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME){throw 'session-0 SSH required'}
if($RunId -ne 'i07-var04-old-cycle-v100-ssh-20261005-01'){throw 'run ID differs from contract'}
if(Test-Path -LiteralPath $run){throw 'immutable run directory occupied'}
if(-not(Test-Path -LiteralPath $work) -or -not(Test-Path -LiteralPath $python)){throw 'pinned runtime path absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$a=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $a){break};$ancestors += $a.Name;$parentPid=$a.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'sshd ancestor required'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
& $python $selectorBuilder | Out-Null
if($LASTEXITCODE -ne 0){throw 'pinned selector verification failed'}
& $python (Join-Path $case 'build.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen child builder verification failed'}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'I07' -or $contract.variant_id -ne 'I07.var04' -or $contract.version -ne '1.0.0-candidate' -or $contract.run_id -ne $RunId -or $contract.source.input_sha256 -ne $sources.input[1] -or $contract.source.builder_sha256 -ne $sources.builder[1] -or $contract.source.roundtrip_checker_sha256 -ne $sources.roundtrip_checker[1] -or $contract.accepted_parent.input_sha256 -ne $sources.parent_input[1] -or $contract.accepted_parent.signoff_sha256 -ne $sources.parent_signoff[1] -or $contract.accepted_parent.event_log_sha256 -ne $sources.parent_event[1]){throw 'frozen contract fields differ'}
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false;$runCreated=$false;$sealed=$false;$steps=@();$fatal=$null
try {
  try{$acquired=$queue.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
  if(-not $acquired){throw 'host-wide native queue busy'}
  Assert-Gui
  $sessions=@(qwinsta 2>&1)
  if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {$_ -match '^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+1\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)'}).Count -ne 1){throw 'GUI session not active'}
  New-Item -ItemType Directory -Path $run -ErrorAction Stop | Out-Null;$runCreated=$true
  Copy-Item -LiteralPath (Join-Path $case 'native-input.json') -Destination (Join-Path $run 'input.json')
  if((Hash (Join-Path $run 'input.json')) -ne $sources.input[1]){throw 'copied input differs'}
  $before=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$before[$entry.Key]=$entry.Value[1]};$before.runner=Hash $PSCommandPath;$before.python=Hash $python
  [ordered]@{schema='simlox-i07-var04-v100-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=1;start_utc='2026-09-28T10:09:56.8261381Z'};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$work;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{roundtrip='not_started';converter_summary=$null;warning_codes=@();result='not_started';error=$null}
  try {
    $sxi=Join-Path $run 'model.sxi';$sxo=Join-Path $run 'model.sxo'
    Run-Simlox 'import' ('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'input.json'),$sxi,(Join-Path $run 'import.log')) (Join-Path $run 'import.log')
    Require-Size 'model.sxi' 4
    Run-Simlox 'export' ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'export.log')) (Join-Path $run 'export.log')
    Require-Size 'roundtrip-raw.json' 1000
    & $python (Join-Path $case 'check_roundtrip.py') (Join-Path $run 'input.json') (Join-Path $run 'roundtrip-raw.json') (Join-Path $run 'roundtrip-check.json') | Out-Null
    if($LASTEXITCODE -ne 0){throw 'exact 22-table roundtrip failed'}
    $outcome.roundtrip='exact'
    Run-Simlox 'calc' ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log')) (Join-Path $run 'run.log')
    Require-Size 'run.log' 4
    $log=Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw -Encoding UTF8
    $m=[regex]::Match($log,'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
    if(-not $m.Success){throw 'converter summary absent'}
    $outcome.converter_summary=@([int]$m.Groups[1].Value,[int]$m.Groups[2].Value,[int]$m.Groups[3].Value)
    $outcome.warning_codes=@([regex]::Matches($log,'\(warning #(\d+)\)') | ForEach-Object {$_.Groups[1].Value})
    if($outcome.converter_summary[0] -ne 0 -or $outcome.converter_summary[1] -ne 2 -or $outcome.converter_summary[2] -ne 0 -or @($outcome.warning_codes).Count -ne 2 -or $outcome.warning_codes[0] -ne '108' -or $outcome.warning_codes[1] -ne '376' -or -not [regex]::IsMatch($log,'(?ms)Form: StockAllocation\s+rec 2: \(warning #376\) ROSIZ not used at location with time-based reorder strategy: TEACH-DU-01 / DEPOT-01')){throw 'frozen converter gate failed'}
    Require-Size 'model.sxo' 1000;Require-Size 'model.log' 1000
    $events=Get-Content -LiteralPath (Join-Path $run 'model.log') -Raw -Encoding UTF8
    if($events -match '(?m)^Time: [5-9](?:\.\d+)? .*?reorder task' -or $events -notmatch '(?m)^Time: 16 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1' -or $events -notmatch '(?m)^Time: 17 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 1 item\(s\) arrives'){throw 'frozen old-cycle event gate failed'}
    Run-Simlox 'report' ('"{0}" -silent -report -rpts "{1}" -rjexport "{2}" -log "{3}" -close' -f $sxo,$selector,(Join-Path $run 'selected-report-raw.json'),(Join-Path $run 'report-export.log')) (Join-Path $run 'report-export.log')
    Require-Size 'selected-report-raw.json' 1000
    $outcome.result='native_run_completed'
  } catch {$outcome.error=$_.Exception.Message}
  $after=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$after[$entry.Key]=Hash $entry.Value[0]};$after.runner=Hash $PSCommandPath;$after.python=Hash $python
  foreach($key in $before.Keys){if($before[$key] -ne $after[$key]){$outcome.error="source changed during run: $key"}}
  $outcome | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-i07-var04-v100-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true;if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;steps=$steps.Count;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-i07-var04-v100-closure/v1';run_id=$RunId;raw=$raw;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

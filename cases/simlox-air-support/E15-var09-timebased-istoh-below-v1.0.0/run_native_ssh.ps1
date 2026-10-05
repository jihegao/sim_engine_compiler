param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$run=Join-Path (Join-Path $case 'runs') $RunId
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$parent=Join-Path (Split-Path $case -Parent) 'E15-var01-time-based-cycle-v1.0.1'
$parentSource=Join-Path (Split-Path $case -Parent) 'E15-var01-time-based-cycle-v1.0.0'
$parentRun=Join-Path (Join-Path $parentSource 'runs') 'e15-var01-timecycle-v100-ssh-20261005-01'
$parentReport=Join-Path (Join-Path $parent 'runs') 'e15-var01-timecycle-report-v101-ssh-20261005-01'
$e02=Join-Path (Split-Path $case -Parent) 'E02-zero-stock-local-backorder-v1.0.0'
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'6497a07693a83d8198342a0423f5b649dbb2bfee98022f03d5a05a5fbd393db2')
  input=@((Join-Path $case 'native-input.json'),'59c8e15370a9b792890e89b157a4a7f88dac30333bcf221fea4824b98dbd7152')
  builder=@((Join-Path $case 'build.py'),'406166c173fabf5f447da127e7766b4c9e1c01fa14ccf671fc84615c86a3737e')
  roundtrip_checker=@((Join-Path $case 'check_roundtrip.py'),'2af10f07debd1588eab42dd0d29d8087876229284d57ceccc9b06b295bb32e82')
  parent_input=@((Join-Path $parentSource 'native-input.json'),'d37bdc10592dff04e521d66276b49f9404dfea0511fac5ea73ef201b02b22b1f')
  parent_signoff=@((Join-Path $parent 'cli-scope-signoff-2026-10-05.md'),'b875964c50598dda9b65dbebb66d9339fa560cf5846b8abc3c345014adbdaa52')
  parent_index=@((Join-Path $parent 'evidence-index.json'),'b29bd16a3ebf1d4bdde6d1a5c743dddda8da82a785d777fdd399a403d8ee5af5')
  parent_event=@((Join-Path $parentRun 'model.log'),'d37165d77f783427b0311c983c3a47f32d3bc7cfc75518063036c03d6c436349')
  parent_report=@((Join-Path $parentReport 'selected-report-raw.json'),'d41c5d0a17e0456453f24bd2c142c2c2c84095ec7e65e7a7e5fdaffdc373c1e0')
  e02_input=@((Join-Path $e02 'native-input.json'),'12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd')
  e02_signoff=@((Join-Path $e02 'cli-scope-signoff-2026-09-29.md'),'c28abcac8c3b8a55d0f58adf87ec3038555102d6b7bc2b35dc84ab9793e42ad6')
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
if($RunId -ne 'e15-var09-istoh-below-v100-ssh-20261005-01'){throw 'run ID differs from contract'}
if(Test-Path -LiteralPath $run){throw 'immutable run directory already exists'}
if(-not(Test-Path -LiteralPath $work)){throw 'pinned working directory absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $ancestor){break};$ancestors += $ancestor.Name;$parentPid=$ancestor.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
& $python (Join-Path $case 'build.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen input builder verification failed'}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'E15' -or $contract.variant_id -ne 'E15.var09' -or $contract.version -ne '1.0.0-candidate' -or $contract.run_id -ne $RunId -or $contract.source.input_sha256 -ne $sources.input[1] -or $contract.source.builder_sha256 -ne $sources.builder[1] -or $contract.source.roundtrip_checker_sha256 -ne $sources.roundtrip_checker[1] -or $contract.accepted_parent.input_sha256 -ne $sources.parent_input[1] -or $contract.accepted_parent.signoff_sha256 -ne $sources.parent_signoff[1] -or $contract.accepted_parent.evidence_index_sha256 -ne $sources.parent_index[1] -or $contract.accepted_parent.event_log_sha256 -ne $sources.parent_event[1] -or $contract.accepted_parent.selected_report_sha256 -ne $sources.parent_report[1] -or $contract.prerequisite_E02.input_sha256 -ne $sources.e02_input[1] -or $contract.prerequisite_E02.signoff_sha256 -ne $sources.e02_signoff[1]){throw 'frozen contract fields differ'}
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
  [ordered]@{schema='simlox-e15-var09-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=1;start_utc='2026-09-28T10:09:56.8261381Z'};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$work;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{import_export='not_started';converter_summary=$null;error_codes=@();diagnostic_lines=@();expected_negative=$false;error=$null}
  try {
    $sxi=Join-Path $run 'model.sxi'
    Run-Simlox 'import' ('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'input.json'),$sxi,(Join-Path $run 'import.log')) (Join-Path $run 'import.log')
    Require-Size 'model.sxi' 4
    Run-Simlox 'export' ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'export.log')) (Join-Path $run 'export.log')
    Require-Size 'roundtrip-raw.json' 1000
    & $python (Join-Path $case 'check_roundtrip.py') (Join-Path $run 'input.json') (Join-Path $run 'roundtrip-raw.json') (Join-Path $run 'roundtrip-check.json') | Out-Null
    if($LASTEXITCODE -ne 0){throw 'exact authored-table roundtrip failed'}
    $outcome.import_export='exact_roundtrip'
    Run-Simlox 'calc_converter_gate' ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log')) (Join-Path $run 'run.log')
    Require-Size 'run.log' 4
    $log=Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw -Encoding UTF8
    $m=[regex]::Match($log,'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
    if(-not $m.Success){throw 'converter summary absent'}
    $outcome.converter_summary=@([int]$m.Groups[1].Value,[int]$m.Groups[2].Value,[int]$m.Groups[3].Value)
    $outcome.error_codes=@([regex]::Matches($log,'\(error #(\d+)\)') | ForEach-Object {$_.Groups[1].Value})
    $outcome.diagnostic_lines=@($log -split "`r?`n" | Where-Object {$_ -match '\(error #\d+\)'})
    if($outcome.converter_summary[0] -lt 1 -or $outcome.error_codes.Count -lt 1){throw 'expected converter error absent'}
    if(-not @($outcome.diagnostic_lines | Where-Object {$_ -match 'ISTOH' -and ($_ -match 'DEPOT-01' -or $_ -match '3')} ).Count){throw 'error not bound to below-nominal ISTOH row or value'}
    $sxo=Join-Path $run 'model.sxo'
    if((Test-Path -LiteralPath $sxo) -and (Get-Item -LiteralPath $sxo).Length -gt 4){throw 'unexpected nonempty simulation output'}
    $outcome.expected_negative=$true
  } catch {$outcome.error=$_.Exception.Message}
  $after=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$after[$entry.Key]=Hash $entry.Value[0]};$after.runner=Hash $PSCommandPath;$after.python=Hash $python
  foreach($key in $before.Keys){if($before[$key] -ne $after[$key]){$outcome.error="source changed during run: $key"}}
  $outcome | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-e15-var09-negative-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;expected_negative=$outcome.expected_negative;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true;if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;steps=$steps.Count;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$partial=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-e15-var09-negative-closure/v1';run_id=$RunId;raw=$partial;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

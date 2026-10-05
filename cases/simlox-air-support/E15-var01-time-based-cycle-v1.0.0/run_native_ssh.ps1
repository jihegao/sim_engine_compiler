param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$root=Split-Path $case -Parent
$e15=Join-Path $root 'E15-var07-explicit-istoh-v1.0.1'
$e02=Join-Path $root 'E02-zero-stock-local-backorder-v1.0.0'
$parentRun=Join-Path (Join-Path $e15 'runs') 'e15-var07-default-v101-ssh-20261002-01'
$parentReportRun=Join-Path (Join-Path $e15 'runs') 'e15-var07-default-item-v101-ssh-20261002-01'
$settingsBuilder=Join-Path $e15 'make_report_settings.py'
$settings=Join-Path (Join-Path $e15 'runs') 'report-settings\item-position-results.sxs'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run=Join-Path (Join-Path $case 'runs') $RunId
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'e5ba51841c45e9ca099d1f063e6c6b48234af01638121bd18b538a8fe9e81965')
  input=@((Join-Path $case 'native-input.json'),'d37bdc10592dff04e521d66276b49f9404dfea0511fac5ea73ef201b02b22b1f')
  builder=@((Join-Path $case 'build.py'),'3c73d81c94788c2247c6f3e7b3640d06cb9b2cddf317f09311a5646429682694')
  roundtrip_checker=@((Join-Path $case 'check_roundtrip.py'),'5b286dcb38a3c4eb5cb61bd4742365933f4fdf1dd94d53628ab6532eeeb5b3b5')
  parent_input=@((Join-Path $e15 'native-input-default.json'),'602dedfdb3491ab430abe4c68426c28203738fe1b2b1173d5d66955d00b6102e')
  parent_signoff=@((Join-Path $e15 'cli-scope-signoff-2026-10-02.md'),'ee38eb8e347ab7e9bd093102c05e0a3d597d7ac692d152bbd1ae00b59bf61a96')
  parent_event=@((Join-Path $parentRun 'model.log'),'f7fb876b752fd8b824defa81bd014fd05a75921d12c352a6940e51b4730bffbf')
  parent_report=@((Join-Path $parentReportRun 'item-report-raw.json'),'d7ed894a40efefc577b0520a4bfb0387d9cb0ea907357eef2e058d1438d96499')
  e02_input=@((Join-Path $e02 'native-input.json'),'12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd')
  e02_signoff=@((Join-Path $e02 'cli-scope-signoff-2026-09-29.md'),'c28abcac8c3b8a55d0f58adf87ec3038555102d6b7bc2b35dc84ab9793e42ad6')
  settings_builder=@($settingsBuilder,'d2ede31eba96985da2e6671ef0f81fe0d010f5e2d6889f09531519e11c73df1e')
  settings=@($settings,'841a6a077741566cac02b84e0cb35f4154f13a857e5665909a483cd6c051316c')
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
if($RunId -ne 'e15-var01-timecycle-v100-ssh-20261005-01'){throw 'run ID differs from contract'}
if(Test-Path -LiteralPath $run){throw 'immutable run directory occupied'}
if(-not(Test-Path -LiteralPath $work) -or -not(Test-Path -LiteralPath $python)){throw 'pinned runtime path absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$a=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $a){break};$ancestors += $a.Name;$parentPid=$a.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'sshd ancestor required'}
if(-not(Test-Path -LiteralPath $settings) -or (Hash $settings) -ne $sources.settings[1]){throw 'accepted report selector absent or changed'}
& $python $settingsBuilder | Out-Null
if($LASTEXITCODE -ne 0){throw 'pinned report selector verification failed'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
& $python (Join-Path $case 'build.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen child builder verification failed'}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'E15' -or $contract.variant_id -ne 'E15.var01' -or $contract.version -ne '1.0.0-candidate' -or $contract.run_id -ne $RunId -or $contract.source.input_sha256 -ne $sources.input[1] -or $contract.source.builder_sha256 -ne $sources.builder[1] -or $contract.source.roundtrip_checker_sha256 -ne $sources.roundtrip_checker[1] -or $contract.prerequisites.E15.input_sha256 -ne $sources.parent_input[1] -or $contract.prerequisites.E02.input_sha256 -ne $sources.e02_input[1] -or $contract.report_selector.settings_sha256 -ne $sources.settings[1]){throw 'frozen contract fields differ'}
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
  [ordered]@{schema='simlox-e15-var01-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=1;start_utc='2026-09-28T10:09:56.8261381Z'};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$work;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{roundtrip='not_started';converter_summary=$null;warning_codes=@();warning_lines=@();result='not_started';error=$null}
  try {
    $sxi=Join-Path $run 'model.sxi';$sxo=Join-Path $run 'model.sxo'
    Run-Simlox 'import' ('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'input.json'),$sxi,(Join-Path $run 'import.log')) (Join-Path $run 'import.log')
    Require-Size 'model.sxi' 4
    Run-Simlox 'export' ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'export.log')) (Join-Path $run 'export.log')
    Require-Size 'roundtrip-raw.json' 1000
    & $python (Join-Path $case 'check_roundtrip.py') (Join-Path $run 'input.json') (Join-Path $run 'roundtrip-raw.json') (Join-Path $run 'roundtrip-check.json') | Out-Null
    if($LASTEXITCODE -ne 0){throw 'exact 21-table roundtrip failed'}
    $outcome.roundtrip='exact'
    Run-Simlox 'calc' ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log')) (Join-Path $run 'run.log')
    Require-Size 'run.log' 4
    $log=Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw -Encoding UTF8
    $m=[regex]::Match($log,'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
    if(-not $m.Success){throw 'converter summary absent'}
    $outcome.converter_summary=@([int]$m.Groups[1].Value,[int]$m.Groups[2].Value,[int]$m.Groups[3].Value)
    $outcome.warning_codes=@([regex]::Matches($log,'\(warning #(\d+)\)') | ForEach-Object {$_.Groups[1].Value})
    $outcome.warning_lines=@($log -split "`r?`n" | Where-Object {$_ -match '\(warning #\d+\)'})
    $ignoredWarning=[regex]::Match($log,'(?ms)Form: ItemReorder\s+rec 1: \(warning #(\d+)\) ([^\r\n]*ROSIZ[^\r\n]*ignor[^\r\n]*)')
    if($outcome.converter_summary[0] -ne 0 -or $outcome.converter_summary[1] -ne 2 -or $outcome.converter_summary[2] -ne 0 -or $outcome.warning_codes.Count -ne 2 -or $outcome.warning_codes[0] -ne '108' -or -not $ignoredWarning.Success -or $ignoredWarning.Groups[1].Value -ne $outcome.warning_codes[1]){throw 'unreviewed converter diagnostic'}
    Require-Size 'model.sxo' 4;Require-Size 'model.log' 4
    Run-Simlox 'selected_report' ('"{0}" -silent -report -rpts "{1}" -rjexport "{2}" -log "{3}" -close' -f $sxo,$settings,(Join-Path $run 'selected-report-raw.json'),(Join-Path $run 'report-export.log')) (Join-Path $run 'report-export.log')
    Require-Size 'selected-report-raw.json' 1000
    $doc=Get-Content -LiteralPath (Join-Path $run 'selected-report-raw.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if(-not $doc.report -or @($doc.report.tables).Count -ne 10){throw 'selected report invalid or incomplete'}
    $outcome.result='completed'
  } catch {$outcome.error=$_.Exception.Message}
  $after=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$after[$entry.Key]=Hash $entry.Value[0]};$after.runner=Hash $PSCommandPath;$after.python=Hash $python
  foreach($key in $before.Keys){if($before[$key] -ne $after[$key]){$outcome.error="source changed during run: $key"}}
  $outcome | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-e15-var01-timecycle-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true;if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;steps=$steps.Count;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-e15-var01-timecycle-closure/v1';run_id=$RunId;raw=$raw;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

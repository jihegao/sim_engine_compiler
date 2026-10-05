param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$root=Split-Path $case -Parent
$parent=Join-Path $root 'E05-local-repair-reissue-v1.0.0'
$parentRun=Join-Path (Join-Path $parent 'runs') 'e05-v100-ssh-20260929-01'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run=Join-Path (Join-Path $case 'runs') $RunId
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'6dca432a09bc441544f21c69aa9f7232bff1c5ebdb430145a9de04e32a4b6d94')
  input=@((Join-Path $case 'native-input.json'),'5d91b1315d1a3d6321285492e8fcd4a3afd61bc8420347713f5646c31cfe5d08')
  builder=@((Join-Path $case 'build.py'),'d6e06f086f85f6ab9483e863f451f847c226a6001536defc70b641350b898e38')
  source_checker=@((Join-Path $case 'check_source.py'),'1ee269a8e2805b73a819d4ed8d0c11cd5df521a100928ba18cf7b8ffd4958c17')
  roundtrip_checker=@((Join-Path $case 'check_roundtrip.py'),'98a927e6f4cb57d405ec2eb9a3ed672a09977300e44411279893795b9d467b4c')
  author_validator=@((Join-Path $case 'validate_native.py'),'80c61f5dd59c9ac4d969570602170d5344aa6b77ce7140a74d02790c1a120ee3')
  ledger_replay=@((Join-Path $case 'ledger_replay.py'),'3bf2e3c711b02c5ba32af47bd539d44b938a0dc030185e4afc944e5bfc934e57')
  shared_validator_module=@((Join-Path (Join-Path $root 'tools') 'validate_native.py'),'43b42fbc5f6d2b9ecbeb82b1419224d6a99025c1be5c600dd959f77d362b6354')
  native_binding_module=@((Join-Path (Join-Path $root 'tools') 'native_binding.py'),'d7cb8cdb670d6ac24536254904d9ac527bee1cfa1d9954dca9bd6a7d9ca0c28a')
  parent_input=@((Join-Path $parent 'native-input.json'),'ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca')
  parent_signoff=@((Join-Path $parent 'cli-scope-signoff-2026-09-29.md'),'e7f4e82be24e09d258345e5f8084ac99e822e8384cb5c8698fbd1ea687105f2f')
  parent_closure=@((Join-Path $parentRun 'closure.json'),'e75836bcd99ba838d4ef247973794a2bf38fbddd4904d69337d631ba983d01ef')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual=@($manual,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
}
function Assert-Gui {
  $p=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne 1 -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne '2026-09-28T10:09:56.8261381Z' -or -not $p[0].Responding){throw 'protected GUI identity or response changed'}
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
if($RunId -ne 'e05-var01-repair-backorder-v102-ssh-20261005-01'){throw 'run ID differs from contract'}
if(Test-Path -LiteralPath $run){throw 'immutable run directory occupied'}
if(-not(Test-Path -LiteralPath $work) -or -not(Test-Path -LiteralPath $python)){throw 'pinned runtime path absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$a=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $a){break};$ancestors += $a.Name;$parentPid=$a.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'sshd ancestor required'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
& $python (Join-Path $case 'build.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen child builder verification failed'}
& $python (Join-Path $case 'check_source.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'accepted parent seal or sole child delta verification failed'}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'E05' -or $contract.variant_id -ne 'E05.var01' -or $contract.version -ne '1.0.2' -or $contract.run_id -ne $RunId -or $contract.native_input_sha256 -ne $sources.input[1] -or $contract.author_validator_sha256 -ne $sources.author_validator[1] -or $contract.ledger_replay_sha256 -ne $sources.ledger_replay[1] -or $contract.shared_validator_module_sha256 -ne $sources.shared_validator_module[1] -or $contract.native_binding_module_sha256 -ne $sources.native_binding_module[1] -or $contract.parent.input_sha256 -ne $sources.parent_input[1] -or $contract.parent.signoff_sha256 -ne $sources.parent_signoff[1] -or $contract.parent.closure_sha256 -ne $sources.parent_closure[1]){throw 'frozen contract fields differ'}
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
  [ordered]@{schema='simlox-e05-var01-v102-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=1;start_utc='2026-09-28T10:09:56.8261381Z'};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$work;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{roundtrip='not_started';converter_summary=$null;warning_codes=@();result='not_started';error=$null}
  try {
    $sxi=Join-Path $run 'model.sxi';$sxo=Join-Path $run 'model.sxo'
    Run-Simlox 'import' ('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'input.json'),$sxi,(Join-Path $run 'import.log')) (Join-Path $run 'import.log')
    Require-Size 'model.sxi' 4
    Run-Simlox 'export' ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'export.log')) (Join-Path $run 'export.log')
    Require-Size 'roundtrip-raw.json' 1000
    & $python (Join-Path $case 'check_roundtrip.py') $run | Set-Content -LiteralPath (Join-Path $run 'roundtrip-check.json') -Encoding UTF8
    if($LASTEXITCODE -ne 0){throw 'exact 20-table roundtrip failed'}
    $outcome.roundtrip='exact'
    Run-Simlox 'calc' ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log')) (Join-Path $run 'run.log')
    Require-Size 'run.log' 4
    $log=Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw -Encoding UTF8
    $m=[regex]::Match($log,'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
    if(-not $m.Success){throw 'converter summary absent'}
    $outcome.converter_summary=@([int]$m.Groups[1].Value,[int]$m.Groups[2].Value,[int]$m.Groups[3].Value)
    $outcome.warning_codes=@([regex]::Matches($log,'\(warning #(\d+)\)') | ForEach-Object {$_.Groups[1].Value})
    if($outcome.converter_summary[0] -ne 0 -or $outcome.converter_summary[1] -ne 1 -or $outcome.converter_summary[2] -ne 0 -or @($outcome.warning_codes).Count -ne 1 -or $outcome.warning_codes[0] -ne '108'){throw 'frozen converter gate failed'}
    Require-Size 'model.sxo' 1000;Require-Size 'model.log' 1000
    Run-Simlox 'report' ('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,(Join-Path $run 'report-raw.json'),(Join-Path $run 'report-export.log')) (Join-Path $run 'report-export.log')
    Require-Size 'report-raw.json' 1000
    $outcome.result='native_run_completed'
  } catch {$outcome.error=$_.Exception.Message}
  $after=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$after[$entry.Key]=Hash $entry.Value[0]};$after.runner=Hash $PSCommandPath;$after.python=Hash $python
  foreach($key in $before.Keys){if($before[$key] -ne $after[$key]){$outcome.error="source changed during run: $key"}}
  $outcome | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-e05-var01-v102-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true;if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;steps=$steps.Count;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-e05-var01-v102-closure/v1';run_id=$RunId;raw=$raw;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

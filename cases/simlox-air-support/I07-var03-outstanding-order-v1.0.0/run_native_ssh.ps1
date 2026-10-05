param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$run=Join-Path (Join-Path $case 'runs') $RunId
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary='C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$parent=Join-Path (Split-Path $case -Parent) 'I07-var01-reorder-lead-time-v1.0.0'
$selectorParent=Join-Path (Split-Path $case -Parent) 'E15-var07-explicit-istoh-v1.0.1'
$roundtripChecker=Join-Path $case 'check_roundtrip.py'
$settingsBuilder=Join-Path $selectorParent 'make_report_settings.py'
$settings=Join-Path (Join-Path $selectorParent 'runs') 'report-settings\item-position-results.sxs'
$defaultSettings='C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs'
$arms=@('late')
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'e511d3ce02d03b594517a0eaeec4d9906a7d06be907e6eba4f9c4ef3ea5dd8c3')
  builder=@((Join-Path $case 'build.py'),'fa38b42bdb549a2c3bfc628d2a8db3360596f30094e5e56d72dec7f203128e8d')
  roundtrip_checker=@($roundtripChecker,'7c723805efb33fb96031a07f9d14f4fafa732a30ee0c319c9d18bdd67354d3a9')
  parent_input=@((Join-Path $parent 'change-input.json'),'4269922f65f8c3ecee867451c2a4c308287c42ebb7c974af93618c7e4e1138e0')
  parent_signoff=@((Join-Path $parent 'cli-scope-signoff-2026-10-05.md'),'65fed727959df7e50542eeea3d97d0af71c166d7e77b3d4c950207f4c64978bd')
  e15_input=@((Join-Path $selectorParent 'native-input-explicit-three.json'),'bb57aecc7285d8eef5c71ba1b7f6b6f7dd9fb4cc46f3e6d88e863eb1da3f206f')
  e15_signoff=@((Join-Path $selectorParent 'cli-scope-signoff-2026-10-02.md'),'ee38eb8e347ab7e9bd093102c05e0a3d597d7ac692d152bbd1ae00b59bf61a96')
  settings_builder=@($settingsBuilder,'d2ede31eba96985da2e6671ef0f81fe0d010f5e2d6889f09531519e11c73df1e')
  default_settings=@($defaultSettings,'1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d')
  selector=@($settings,'841a6a077741566cac02b84e0cb35f4154f13a857e5665909a483cd6c051316c')
  parent_index=@((Join-Path $parent 'evidence-index.json'),'0397256f6b190cba91a5c9aad2dc1388053aa304861a8411d8e41d2212050382')
  parent_closure=@((Join-Path (Join-Path $parent 'runs') 'i07-var01-reorder-leadt-v100-ssh-20261005-01\closure.json'),'321a06fdd1b3fd505ba6f2a4748b9cc19fcad8eadbff1169fbc3746dde9462f9')
  late=@((Join-Path $case 'late-input.json'),'82942e5b7dedefba724edfac4e560b4cebab3c1c01a855050cfb8e24efe2ff4b')
  exe=@($exe,'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual=@($manual,'39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
  dictionary=@($dictionary,'11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0')
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
if($RunId -ne 'i07-var03-outstanding-v100-ssh-20261005-01'){throw 'run ID differs from contract'}
if(Test-Path -LiteralPath $run){throw 'immutable run directory already exists'}
if(-not(Test-Path -LiteralPath $work)){throw 'pinned working directory absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $ancestor){break};$ancestors += $ancestor.Name;$parentPid=$ancestor.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
& $python $settingsBuilder | Out-Null
if($LASTEXITCODE -ne 0){throw 'pinned report selector verification failed'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
& $python (Join-Path $case 'build.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen input builder verification failed'}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'I07' -or $contract.variant_id -ne 'I07.var03' -or $contract.version -ne '1.0.0-candidate' -or $contract.run_id -ne $RunId -or $contract.source.builder_sha256 -ne $sources.builder[1] -or $contract.source.roundtrip_checker_sha256 -ne $sources.roundtrip_checker[1] -or $contract.source.input_sha256 -ne $sources.late[1] -or $contract.parents.I07_var01.input_sha256 -ne $sources.parent_input[1] -or $contract.parents.I07_var01.signoff_sha256 -ne $sources.parent_signoff[1] -or $contract.parents.I07_var01.evidence_index_sha256 -ne $sources.parent_index[1] -or $contract.parents.I07_var01.run_closure_sha256 -ne $sources.parent_closure[1] -or $contract.parents.E15.input_sha256 -ne $sources.e15_input[1] -or $contract.parents.E15.signoff_sha256 -ne $sources.e15_signoff[1] -or $contract.source.manual_pdf_sha256 -ne $sources.manual[1] -or $contract.source.dictionary_sha256 -ne $sources.dictionary[1] -or $contract.report_selector.builder_sha256 -ne $sources.settings_builder[1] -or $contract.report_selector.default_sha256 -ne $sources.default_settings[1] -or $contract.report_selector.selector_sha256 -ne $sources.selector[1]){throw 'frozen contract fields differ'}
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
  [ordered]@{schema='simlox-i07-outstanding-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$work;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{arms=[ordered]@{};converter_summaries=[ordered]@{};warning_codes=[ordered]@{};error=$null}
  foreach($arm in $arms){$outcome.arms[$arm]='not_started'}
  try {
    foreach($arm in $arms){
      $sxi=Join-Path $run "$arm.sxi";$sxo=Join-Path $run "$arm.sxo"
      Run-Simlox "${arm}_import" ('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run "$arm-input.json"),$sxi,(Join-Path $run "$arm-import.log")) (Join-Path $run "$arm-import.log")
      Require-Size "$arm.sxi" 4
      Run-Simlox "${arm}_export" ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run "$arm-roundtrip-raw.json"),(Join-Path $run "$arm-export.log")) (Join-Path $run "$arm-export.log")
      Require-Size "$arm-roundtrip-raw.json" 1000
      & $python $roundtripChecker (Join-Path $run "$arm-input.json") (Join-Path $run "$arm-roundtrip-raw.json") (Join-Path $run "$arm-roundtrip-check.json") | Out-Null
      if($LASTEXITCODE -ne 0){throw "$arm exact authored-table roundtrip failed"}
      Require-Size "$arm-roundtrip-check.json" 50
      Run-Simlox "${arm}_calc" ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run "$arm-run.log")) (Join-Path $run "$arm-run.log")
      Require-Size "$arm-run.log" 4
      $log=Get-Content -LiteralPath (Join-Path $run "$arm-run.log") -Raw -Encoding UTF8
      $m=[regex]::Match($log,'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
      if(-not $m.Success){throw "$arm converter summary absent"}
      $outcome.converter_summaries[$arm]=@([int]$m.Groups[1].Value,[int]$m.Groups[2].Value,[int]$m.Groups[3].Value)
      $warningCodes=@([regex]::Matches($log,'\(warning #(\d+)\)') | ForEach-Object {$_.Groups[1].Value})
      $outcome.warning_codes[$arm]=$warningCodes
      if([int]$m.Groups[1].Value -ne 0 -or [int]$m.Groups[2].Value -ne 1 -or [int]$m.Groups[3].Value -ne 0 -or $warningCodes.Count -ne 1 -or $warningCodes[0] -ne '108'){throw "$arm unreviewed converter diagnostic"}
      Require-Size "$arm.sxo" 4;Require-Size "$arm.log" 4
      Run-Simlox "${arm}_report" ('"{0}" -silent -report -rpts "{1}" -rjexport "{2}" -log "{3}" -close' -f $sxo,$settings,(Join-Path $run "$arm-report-raw.json"),(Join-Path $run "$arm-report-export.log")) (Join-Path $run "$arm-report-export.log")
      Require-Size "$arm-report-raw.json" 1000
      $outcome.arms[$arm]='completed'
    }
  } catch {$outcome.error=$_.Exception.Message}
  $after=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$after[$entry.Key]=Hash $entry.Value[0]};$after.runner=Hash $PSCommandPath;$after.python=Hash $python
  foreach($key in $before.Keys){if($before[$key] -ne $after[$key]){$outcome.error="source changed during run: $key"}}
  $outcome | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-i07-outstanding-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true;if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;steps=$steps.Count;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$partial=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-i07-outstanding-closure/v1';run_id=$RunId;raw=$partial;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,79}$')][string]$RunId)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$run=Join-Path (Join-Path $case 'runs') $RunId
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$parent=Join-Path (Split-Path $case -Parent) 'E14-var01-02-extra-removal-v1.0.0'
$parentRun=Join-Path (Join-Path $parent 'runs') 'e14-var01-02-two-sru-panel-v100-ssh-20261005-01'
$e05=Join-Path (Split-Path $case -Parent) 'E05-local-repair-reissue-v1.0.0'
$repo=Split-Path (Split-Path (Split-Path $case -Parent) -Parent) -Parent
$sources=[ordered]@{
  contract=@((Join-Path $case 'contract.json'),'8f515252cfa21a317b5d1b19d43467db28c84c8a22c29b3bd797ea2b5fb4f54e')
  input=@((Join-Path $case 'native-input.json'),'27e5d18f5b6bc4b88e3615c0cac229b9886ecfdb4ac5b543da30cb660a33c8a1')
  builder=@((Join-Path $case 'build.py'),'77b720971fd93274b35f4205b19ab60378a71c3dd76fc2c920ea1551502f1d44')
  roundtrip_checker=@((Join-Path $case 'check_roundtrip.py'),'5bd70ac61656c183111af2aeab8af477ca49920acbaf67074fbea68135e3b15a')
  parent_index_verifier=@((Join-Path $case 'verify_parent_index.py'),'52c1a1bd9a8a14c2f000d6ff4f0709231be3632fdef7ed7b7ca06554e794fbc2')
  parent_input=@((Join-Path $parent 'seed2-extra-input.json'),'531a1f99e45b71ad0137aaf18650e3df84cec77a677beadaad7d35e4fdb84a75')
  parent_signoff=@((Join-Path $parent 'cli-scope-signoff-2026-10-05.md'),'03de3a793b4dce78c03243d949337988a83c42d137021c13ac0d1812e98b9d5e')
  parent_index=@((Join-Path $parent 'evidence-index.json'),'7f2318d933bc0281aac2b70c82d65fae0b97c6b4c08d5a7cb8b0cb6913f7d684')
  parent_closure=@((Join-Path $parentRun 'closure.json'),'a89e5ef615ff2fb9f3eb5205e9d6e8b45a8770c755f42aec9d68a6155aef6bdb')
  parent_event=@((Join-Path $parentRun 'seed2-extra.log'),'266bf98e5c883afbf297be14f10ec700b112f2dfb648d939e2d5b7c1671dec05')
  parent_sxo=@((Join-Path $parentRun 'seed2-extra.sxo'),'739231b2ca33e4093399e42aa9b900b6f41aee4e13530274a344149bde61adfc')
  e05_input=@((Join-Path $e05 'native-input.json'),'ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca')
  e05_signoff=@((Join-Path $e05 'cli-scope-signoff-2026-09-29.md'),'e7f4e82be24e09d258345e5f8084ac99e822e8384cb5c8698fbd1ea687105f2f')
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
if($RunId -ne 'e14-var05-nfff-over-rrf-v100-ssh-20261005-01'){throw 'run ID differs from contract'}
if(Test-Path -LiteralPath $run){throw 'immutable run directory already exists'}
if(-not(Test-Path -LiteralPath $work)){throw 'pinned working directory absent'}
$ancestors=@();$parentPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $parentPid -gt 0;$depth++){$ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid";if(-not $ancestor){break};$ancestors += $ancestor.Name;$parentPid=$ancestor.ParentProcessId}
if($ancestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
foreach($entry in $sources.GetEnumerator()){$path,$expected=$entry.Value;if(-not(Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected){throw "source fingerprint differs: $($entry.Key)"}}
$parentIndexCommit='94a6dcdf6d175e98a00ffdf9c0fdc2a0102cd962'
$parentIndexGitSha='9e12915cdc2679f04d84cab7113311b761396df5f86e937b3ea6f84037272942'
& $python $sources.parent_index_verifier[0] $repo "${parentIndexCommit}:cases/simlox-air-support/E14-var01-02-extra-removal-v1.0.0/evidence-index.json" $sources.parent_index[0] $sources.parent_index[1] 33683 $parentIndexGitSha 32883 | Out-Null
if($LASTEXITCODE -ne 0){throw 'published parent index Git bytes or CRLF relation differ'}
& $python (Join-Path $case 'build.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'frozen input builder verification failed'}
$contract=Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($contract.case_id -ne 'E14' -or $contract.variant_id -ne 'E14.var05' -or $contract.version -ne '1.0.0-candidate' -or $contract.run_id -ne $RunId -or $contract.source.input_sha256 -ne $sources.input[1] -or $contract.source.builder_sha256 -ne $sources.builder[1] -or $contract.source.roundtrip_checker_sha256 -ne $sources.roundtrip_checker[1] -or $contract.source.parent_index_verifier_sha256 -ne $sources.parent_index_verifier[1] -or $contract.accepted_parent.input_sha256 -ne $sources.parent_input[1] -or $contract.accepted_parent.signoff_sha256 -ne $sources.parent_signoff[1] -or $contract.accepted_parent.evidence_index_sha256 -ne $sources.parent_index[1] -or $contract.accepted_parent.evidence_index_local_bytes -ne 33683 -or $contract.accepted_parent.evidence_index_published_git_sha256 -ne $parentIndexGitSha -or $contract.accepted_parent.evidence_index_published_git_bytes -ne 32883 -or $contract.accepted_parent.evidence_index_published_commit -ne $parentIndexCommit -or $contract.accepted_parent.native_closure_sha256 -ne $sources.parent_closure[1] -or $contract.accepted_parent.seed2_extra_event_sha256 -ne $sources.parent_event[1] -or $contract.accepted_parent.seed2_extra_sxo_sha256 -ne $sources.parent_sxo[1] -or $contract.catalog_prerequisite.input_sha256 -ne $sources.e05_input[1] -or $contract.catalog_prerequisite.signoff_sha256 -ne $sources.e05_signoff[1]){throw 'frozen contract fields differ'}
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
  [ordered]@{schema='simlox-e14-var05-invocation/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');run_dir=$run;session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=1;start_utc='2026-09-28T10:09:56.8261381Z'};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$work;source_hashes_before=$before;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $outcome=[ordered]@{import_export='not_started';import_diagnostic=$null;expected_negative=$false;error=$null}
  try {
    $sxi=Join-Path $run 'model.sxi'
    Run-Simlox 'import' ('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'input.json'),$sxi,(Join-Path $run 'import.log')) (Join-Path $run 'import.log')
    Require-Size 'model.sxi' 4
    Run-Simlox 'export' ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'export.log')) (Join-Path $run 'export.log')
    Require-Size 'roundtrip-raw.json' 1000
    & $python (Join-Path $case 'check_roundtrip.py') (Join-Path $run 'input.json') (Join-Path $run 'roundtrip-raw.json') (Join-Path $run 'roundtrip-check.json') | Out-Null
    if($LASTEXITCODE -ne 0){throw 'unexpected authored-table difference beyond target NFFF erasure'}
    $outcome.import_export='target_nfff_erased_only'
    $log=Get-Content -LiteralPath (Join-Path $run 'import.log') -Raw -Encoding UTF8
    $diagnostics=@([regex]::Matches($log,'Value \([^)]*\) in record:\s*\d+, Column:\s*\S+ Table:\s*\S+ cannot be imported[^\r\n]*') | ForEach-Object {$_.Value})
    if($diagnostics.Count -ne 1 -or $diagnostics[0] -notmatch '^Value \(5(?:\.0+)?\) in record:\s*2, Column:\s*NFFF Table:\s*ItemStructure cannot be imported'){throw 'sole targeted NFFF5 import rejection absent or accompanied by another rejection'}
    $outcome.import_diagnostic=$diagnostics[0]
    foreach($unexpected in @('model.sxo','model.log','run.log','selected-report-raw.json')){if(Test-Path -LiteralPath (Join-Path $run $unexpected)){throw "unexpected calculation or report output: $unexpected"}}
    $outcome.expected_negative=$true
  } catch {$outcome.error=$_.Exception.Message}
  $after=[ordered]@{};foreach($entry in $sources.GetEnumerator()){$after[$entry.Key]=Hash $entry.Value[0]};$after.runner=Hash $PSCommandPath;$after.python=Hash $python
  foreach($key in $before.Keys){if($before[$key] -ne $after[$key]){$outcome.error="source changed during run: $key"}}
  $outcome | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'outcome.json') -Encoding UTF8
  $raw=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}}
  [ordered]@{schema='simlox-e14-var05-negative-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$before;source_hashes_after=$after;raw=$raw;expected_negative=$outcome.expected_negative;error=$outcome.error;publication_state='not_published'} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $sealed=$true;if($outcome.error){throw $outcome.error}
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;steps=$steps.Count;outcome=$outcome} | ConvertTo-Json -Depth 5)
} catch {$fatal=$_.Exception.Message;throw}
finally {
  if($runCreated -and -not $sealed -and -not(Test-Path -LiteralPath (Join-Path $run 'closure.json'))){
    try{$partial=[ordered]@{};foreach($file in Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notin @('invocation.json','closure.json')}){$partial[$file.Name]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName}};[ordered]@{schema='simlox-e14-var05-negative-closure/v1';run_id=$RunId;raw=$partial;error=$fatal;partial=$true;publication_state='excluded_diagnostic'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8}catch{Write-Error "partial closure failed: $($_.Exception.Message)"}
  }
  if($acquired){$queue.ReleaseMutex() | Out-Null};$queue.Dispose()
}

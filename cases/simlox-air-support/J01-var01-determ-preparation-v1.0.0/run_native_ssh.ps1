param(
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$InputSha256,
 [switch]$AllowExistingGui
)
$ErrorActionPreference='Stop'
Write-Output 'J01.var01 preflight: entry'
$case=(Resolve-Path $PSScriptRoot).Path
$runnerPath=$PSCommandPath
Write-Output 'J01.var01 preflight: case path resolved'
$input=Join-Path $case 'native-input.json'
$inputPath=$input
$contractPath=Join-Path $case 'contract.json'
$caseVersion='1.0.0'
$parentInput=Join-Path (Join-Path (Split-Path $case -Parent) 'B01-fixed-preparation-v1.0.1') 'native-input.json'
$parentDiff=Join-Path $case 'parent-diff.json'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$exeSha256='fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
$expectedGuiStartUtc='2026-09-28T10:09:56.8261381Z'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$python='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\py312-venv\Scripts\python.exe'
$base=Join-Path $case 'runs'
$run=Join-Path $base $RunId
if(Test-Path -LiteralPath $run){throw "immutable run directory exists: $run"}
if(-not $AllowExistingGui){throw 'J01.var01 run requires explicit coexistence with GUI PID 13340'}
Write-Output 'J01.var01 preflight: fresh run ID and GUI coexistence requested'
$sshSessionPresent=[bool]$env:SSH_CONNECTION
if(-not $sshSessionPresent){throw 'SSH CLI runner requires an authenticated SSH session'}
$executionSessionId=(Get-Process -Id $PID).SessionId
if($executionSessionId -ne 0 -or $env:SESSIONNAME){throw 'SSH CLI runner requires a session-0 SSH process'}
Write-Output 'J01.var01 preflight: session 0 verified'
$sshAncestors=@()
$ancestorPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++){
 $ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
 if(-not $ancestor){break}
 $sshAncestors += $ancestor.Name
 $ancestorPid=$ancestor.ParentProcessId
}
if($sshAncestors -notcontains 'sshd.exe'){throw 'SSH CLI runner cannot verify an sshd ancestor'}
Write-Output 'J01.var01 preflight: SSH session-0 ancestry verified'
if(!(Test-Path -LiteralPath $workingDirectory) -or !(Test-Path -LiteralPath $python)){throw 'known native runtime dependencies absent'}
if(!(Test-Path -LiteralPath $exe) -or (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $exeSha256){throw 'SIMLOX executable fingerprint changed'}
if((Get-FileHash -LiteralPath $input -Algorithm SHA256).Hash.ToLowerInvariant() -ne $InputSha256){throw 'checked input fingerprint changed'}
$contract=Get-Content -LiteralPath $contractPath -Raw | ConvertFrom-Json
if($contract.version -ne $caseVersion -or $contract.case_id -ne 'J01' -or $contract.variant_id -ne 'J01.var01' -or $contract.input_sha256 -ne $InputSha256){throw 'J01.var01 contract and input fingerprint differ'}
foreach($source in @(@($contract.source.database_dictionary,$contract.source.database_dictionary_sha256),@($contract.source.manual,$contract.source.manual_sha256))){
 if(!(Test-Path -LiteralPath $source[0]) -or (Get-FileHash -LiteralPath $source[0] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $source[1]){throw "installed source fingerprint changed: $($source[0])"}
}
if((Get-FileHash -LiteralPath $parentInput -Algorithm SHA256).Hash.ToLowerInvariant() -ne $contract.parent_input_sha256){throw 'frozen B01 input fingerprint changed'}
if((Get-FileHash -LiteralPath $parentDiff -Algorithm SHA256).Hash.ToLowerInvariant() -ne $contract.parent_diff_sha256){throw 'exact parent diff fingerprint changed'}
& $python (Join-Path $case 'build.py') --check | Out-Null
if($LASTEXITCODE -ne 0){throw 'J01.var01 input or parent diff fails builder check'}
Write-Output 'J01.var01 preflight: source and parent hashes verified'
$queueMutexName='Global\SimloxIssue18NativeQueue'
$queueMutex=New-Object System.Threading.Mutex($false,$queueMutexName)
$queueAcquired=$false
function Seal-Run([string]$state){
 $raw=[ordered]@{}
 foreach($name in @('input.json','roundtrip-raw.json','model.sxi','model.sxo','import.log','export.log','run.log','model.log','report-raw.json','report-export.log','steps.json')){
  $path=Join-Path $run $name
  if(Test-Path -LiteralPath $path){$raw[$name]=[ordered]@{bytes=(Get-Item -LiteralPath $path).Length;sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}}
 }
 $sources=[ordered]@{}
 foreach($entry in @(
  @('native-input.json',$inputPath),@('contract.json',$contractPath),@('build.py',(Join-Path $case 'build.py')),
  @('validate.py',(Join-Path $case 'validate.py')),@('run_native_ssh.ps1',$runnerPath),
  @('parent-diff.json',$parentDiff),@('parent-input.json',$parentInput),
  @('database-dictionary.txt',$contract.source.database_dictionary),@('manual.pdf',$contract.source.manual)
 )){
  if(Test-Path -LiteralPath $entry[1]){$sources[$entry[0]]=(Get-FileHash -LiteralPath $entry[1] -Algorithm SHA256).Hash.ToLowerInvariant()}
 }
 $invocationPath=Join-Path $run 'invocation.json'
 $invocationHash=if(Test-Path -LiteralPath $invocationPath){(Get-FileHash -LiteralPath $invocationPath -Algorithm SHA256).Hash.ToLowerInvariant()}else{$null}
 [ordered]@{schema='simlox-j01-var01-closure/v1';case_id='J01';case_version=$caseVersion;run_id=$RunId;
  state=$state;input_sha256=$InputSha256;invocation_sha256=$invocationHash;raw=$raw;post_source_sha256=$sources
 }|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
}
try {
try {$queueAcquired=$queueMutex.WaitOne(0)}
catch [System.Threading.AbandonedMutexException] {$queueAcquired=$true}
if(-not $queueAcquired){throw 'another Issue #18 SSH native runner holds the host-wide queue mutex'}
Write-Output 'J01.var01 preflight: native queue mutex acquired'
$existing=@(Get-Process Simlox -ErrorAction SilentlyContinue)
$coexistingGui=$null
if($existing.Count -gt 0){
 if(-not $AllowExistingGui -or $existing.Count -ne 1){throw 'SIMLOX already active; explicit single-GUI coexistence is required'}
 $gui=$existing[0]
 if($gui.Id -ne 13340 -or $gui.StartTime.ToUniversalTime().ToString('o') -ne $expectedGuiStartUtc){throw 'existing SIMLOX GUI is not the preserved PID 13340 process'}
 if(-not $gui.Responding){throw 'preserved SIMLOX GUI is not responding'}
 $guiSessionId=$gui.SessionId
 if($guiSessionId -le 0){throw 'existing SIMLOX process is not an interactive GUI'}
 $sessionRows=@(qwinsta 2>&1)
 if($LASTEXITCODE -ne 0){throw 'cannot verify the GUI session'}
 $guiRows=@($sessionRows | Where-Object {$_ -match ('^\s*>?\s*(?:\S+\s+)?'+[regex]::Escape($env:USERNAME)+'\s+'+$guiSessionId+'\s+(?:Active|Disc|\u8fd0\u884c\u4e2d|\u65ad\u5f00)(?:\s|$)')})
 if($guiRows.Count -ne 1){throw 'cannot bind preserved GUI to one logged-on interactive session'}
 $coexistingGui=[ordered]@{pid=$gui.Id;session_id=$guiSessionId;session_query_line=$guiRows[0].Trim();process_start_utc=$gui.StartTime.ToUniversalTime().ToString('o');responding_at_preflight=[bool]$gui.Responding}
}elseif($AllowExistingGui){throw 'AllowExistingGui was requested without an existing GUI'}
Write-Output 'J01.var01 preflight: GUI PID 13340 and logged-on session verified'
New-Item -ItemType Directory -Path $run -Force | Out-Null
Write-Output "J01.var01 preflight: run directory created at $run"
Copy-Item -LiteralPath $input -Destination (Join-Path $run 'input.json')
$source=Join-Path $run 'input.json'
$sxi=Join-Path $run 'model.sxi'
$sxo=Join-Path $run 'model.sxo'
$round=Join-Path $run 'roundtrip-raw.json'
$report=Join-Path $run 'report-raw.json'
$invocation=[ordered]@{
 schema='simlox-j01-var01-invocation/ssh-cli-v1';case_id='J01';case_version=$caseVersion;run_id=$RunId
 created_utc=(Get-Date).ToUniversalTime().ToString('o')
 original_run_dir=$run;host_name=$env:COMPUTERNAME
 input_sha256=$InputSha256;contract_sha256=(Get-FileHash (Join-Path $case 'contract.json') -Algorithm SHA256).Hash.ToLowerInvariant()
 parent_input_sha256=$contract.parent_input_sha256;parent_diff_sha256=$contract.parent_diff_sha256
 builder_sha256=(Get-FileHash (Join-Path $case 'build.py') -Algorithm SHA256).Hash.ToLowerInvariant()
 validator_sha256=(Get-FileHash (Join-Path $case 'validate.py') -Algorithm SHA256).Hash.ToLowerInvariant()
 runner_sha256=(Get-FileHash $runnerPath -Algorithm SHA256).Hash.ToLowerInvariant()
 simlox_exe_sha256=$exeSha256;working_directory=$workingDirectory
 execution_mode='ssh_cli_v1';session_name=$env:SESSIONNAME;session_id=$executionSessionId
 ssh_connection_present=[bool]$env:SSH_CONNECTION;ssh_client_present=[bool]$env:SSH_CLIENT
 ssh_ancestor_names=$sshAncestors
 allow_existing_gui=[bool]$AllowExistingGui;coexisting_gui=$coexistingGui
 queue_mutex=$queueMutexName
}
$invocation|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
$invocationSha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant()
$commands=@(
 [pscustomobject]@{name='import';args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $source,$sxi,(Join-Path $run 'import.log'))},
 [pscustomobject]@{name='export';args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,$round,(Join-Path $run 'export.log'))},
 [pscustomobject]@{name='calc';args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log'))},
 [pscustomobject]@{name='jsonreport';args=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,$report,(Join-Path $run 'report-export.log'))}
)
$steps=@()
foreach($command in $commands){
 $present=@(Get-Process Simlox -ErrorAction SilentlyContinue)
 if($coexistingGui){
  if($present.Count -ne 1 -or $present[0].Id -ne $coexistingGui.pid -or $present[0].StartTime.ToUniversalTime().ToString('o') -ne $coexistingGui.process_start_utc){throw 'SIMLOX process set changed before serial queue item'}
 }elseif($present.Count -ne 0){throw 'SIMLOX appeared during serial queue item'}
 $watch=[Diagnostics.Stopwatch]::StartNew()
 $startedUtc=(Get-Date).ToUniversalTime().ToString('o')
 $process=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru
 if(-not $process.WaitForExit(120000)){
  Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
  $process.WaitForExit()
  throw "native $($command.name) exceeded 120 seconds; preserved run directory"
 }
 $watch.Stop()
 $completedUtc=(Get-Date).ToUniversalTime().ToString('o')
 $after=@(Get-Process Simlox -ErrorAction SilentlyContinue)
 $guiStillPresent=($coexistingGui -and $after.Count -eq 1 -and $after[0].Id -eq $coexistingGui.pid -and $after[0].StartTime.ToUniversalTime().ToString('o') -eq $coexistingGui.process_start_utc)
 $steps += [pscustomobject]@{name=$command.name;arguments=$command.args;exit_code=$process.ExitCode;wall_seconds=$watch.Elapsed.TotalSeconds;started_utc=$startedUtc;completed_utc=$completedUtc;coexisting_gui_present_after=[bool]$guiStillPresent}
 $steps|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
 if($coexistingGui -and -not $guiStillPresent){throw 'existing GUI process changed during native command'}
 if($process.ExitCode -ne 0){throw "$($command.name) exited $($process.ExitCode); preserve run directory"}
 if($command.name -eq 'import' -and (!(Test-Path $sxi) -or (Get-Item $sxi).Length -le 4)){throw 'empty SXI'}
 if($command.name -eq 'export' -and (!(Test-Path $round) -or (Get-Item $round).Length -le 4)){throw 'empty roundtrip export'}
 if($command.name -eq 'calc'){
  if(!(Test-Path $sxo) -or (Get-Item $sxo).Length -le 4){throw 'empty SXO; report export withheld'}
  $conversion=[regex]::Match((Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw), 'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
  if(-not $conversion.Success -or [int]$conversion.Groups[1].Value -ne 0){throw 'converter error or missing conversion summary; report export withheld'}
 }
 if($command.name -eq 'jsonreport' -and (!(Test-Path $report) -or (Get-Item $report).Length -le 4)){throw 'empty report'}
}
foreach($name in @('input.json','roundtrip-raw.json','model.sxi','model.sxo','import.log','export.log','run.log','model.log','report-raw.json','report-export.log','steps.json')){
 $path=Join-Path $run $name
 if(!(Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -le 4){throw "missing raw artifact: $name"}
}
Seal-Run 'native_steps_complete'
& $python (Join-Path $case 'validate.py') $run | Set-Content -LiteralPath (Join-Path $run 'validation.json') -Encoding UTF8
if($LASTEXITCODE -ne 0){throw 'J01.var01 CLI assertions failed; preserve raw artifacts'}
[ordered]@{schema='simlox-j01-var01-run-manifest/v1';case_id='J01';case_version=$caseVersion;run_id=$RunId;input_sha256=$InputSha256;invocation_sha256=$invocationSha256;closure_sha256=(Get-FileHash (Join-Path $run 'closure.json') -Algorithm SHA256).Hash.ToLowerInvariant();validation_sha256=(Get-FileHash (Join-Path $run 'validation.json') -Algorithm SHA256).Hash.ToLowerInvariant();execution_mode='ssh_cli_v1';acceptance_scope='candidate_cli_review';publication_state='not_published';gui_status='preserved_pid_13340'}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $run 'run-manifest.json') -Encoding UTF8
$steps|Format-Table name,exit_code,wall_seconds -AutoSize
} finally {
 if((Test-Path -LiteralPath $run) -and -not (Test-Path -LiteralPath (Join-Path $run 'closure.json'))){Seal-Run 'partial_native_probe'}
 if($queueAcquired){$queueMutex.ReleaseMutex()|Out-Null}
 $queueMutex.Dispose()
}

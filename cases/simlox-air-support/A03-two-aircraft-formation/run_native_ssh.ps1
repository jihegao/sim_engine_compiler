param(
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$InputSha256,
 [switch]$AllowExistingGui
)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$input=Join-Path $case 'native-input.json'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$exeSha256='fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$python='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\py312-venv\Scripts\python.exe'
$base=Join-Path $case 'runs'
$run=Join-Path $base $RunId
if(Test-Path -LiteralPath $run){throw "immutable run directory exists: $run"}
$sshSessionPresent=[bool]$env:SSH_CONNECTION
if(-not $sshSessionPresent){throw 'SSH CLI runner requires an authenticated SSH session'}
$executionSessionId=(Get-Process -Id $PID).SessionId
if($executionSessionId -ne 0 -or $env:SESSIONNAME){throw 'SSH CLI runner requires a session-0 SSH process'}
$sshAncestors=@()
$ancestorPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++){
 $ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
 if(-not $ancestor){break}
 $sshAncestors += $ancestor.Name
 $ancestorPid=$ancestor.ParentProcessId
}
if($sshAncestors -notcontains 'sshd.exe'){throw 'SSH CLI runner cannot verify an sshd ancestor'}
if(!(Test-Path -LiteralPath $workingDirectory) -or !(Test-Path -LiteralPath $python)){throw 'known native runtime dependencies absent'}
if(!(Test-Path -LiteralPath $exe) -or (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $exeSha256){throw 'SIMLOX executable fingerprint changed'}
if((Get-FileHash -LiteralPath $input -Algorithm SHA256).Hash.ToLowerInvariant() -ne $InputSha256){throw 'checked input fingerprint changed'}
$queueMutexName='Global\SimloxIssue18NativeQueue'
$queueMutex=New-Object System.Threading.Mutex($false,$queueMutexName)
$queueAcquired=$false
try {
try {$queueAcquired=$queueMutex.WaitOne(0)}
catch [System.Threading.AbandonedMutexException] {$queueAcquired=$true}
if(-not $queueAcquired){throw 'another Issue #18 SSH native runner holds the host-wide queue mutex'}
$existing=@(Get-Process Simlox -ErrorAction SilentlyContinue)
$coexistingGui=$null
if($existing.Count -gt 0){
 if(-not $AllowExistingGui -or $existing.Count -ne 1){throw 'SIMLOX already active; explicit single-GUI coexistence is required'}
 $gui=$existing[0]
 $guiSessionId=$gui.SessionId
 if($guiSessionId -le 0){throw 'existing SIMLOX process is not an interactive GUI'}
 $sessionRows=@(qwinsta 2>&1)
 if($LASTEXITCODE -ne 0){throw 'cannot verify the GUI session'}
 $activeGuiRows=@($sessionRows | Where-Object {$_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSessionId+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)')})
 if($activeGuiRows.Count -ne 1){throw 'existing SIMLOX GUI is not in one active interactive session'}
 $coexistingGui=[ordered]@{pid=$gui.Id;session_id=$guiSessionId;session_query_line=$activeGuiRows[0].Trim();process_start_utc=$gui.StartTime.ToUniversalTime().ToString('o')}
}elseif($AllowExistingGui){throw 'AllowExistingGui was requested without an existing GUI'}
New-Item -ItemType Directory -Path $run -Force | Out-Null
Copy-Item -LiteralPath $input -Destination (Join-Path $run 'input.json')
$source=Join-Path $run 'input.json'
$sxi=Join-Path $run 'model.sxi'
$sxo=Join-Path $run 'model.sxo'
$round=Join-Path $run 'roundtrip-raw.json'
$report=Join-Path $run 'report-raw.json'
$invocation=[ordered]@{
 schema='simlox-a03-invocation/ssh-cli-v1';case_id='A03';run_id=$RunId
 created_utc=(Get-Date).ToUniversalTime().ToString('o')
 original_run_dir=$run;host_name=$env:COMPUTERNAME
 input_sha256=$InputSha256;contract_sha256=(Get-FileHash (Join-Path $case 'contract.json') -Algorithm SHA256).Hash.ToLowerInvariant()
 validator_sha256=(Get-FileHash (Join-Path $case 'validate.py') -Algorithm SHA256).Hash.ToLowerInvariant()
 strict_validator_sha256=(Get-FileHash (Join-Path $case 'validate_strict.py') -Algorithm SHA256).Hash.ToLowerInvariant()
 runner_sha256=(Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
 simlox_exe_sha256=$exeSha256;working_directory=$workingDirectory
 execution_mode='ssh_cli_v1';session_name=$env:SESSIONNAME;session_id=$executionSessionId
 ssh_connection_present=[bool]$env:SSH_CONNECTION;ssh_client_present=[bool]$env:SSH_CLIENT
 ssh_ancestor_names=$sshAncestors
 allow_existing_gui=[bool]$AllowExistingGui;coexisting_gui=$coexistingGui
 queue_mutex=$queueMutexName
}
$invocation|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
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
 $process=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
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
 if($command.name -eq 'calc' -and (!(Test-Path $sxo) -or (Get-Item $sxo).Length -le 4)){throw 'empty SXO'}
 if($command.name -eq 'jsonreport' -and (!(Test-Path $report) -or (Get-Item $report).Length -le 4)){throw 'empty report'}
}
$raw=@{}
foreach($name in @('input.json','roundtrip-raw.json','model.sxi','model.sxo','import.log','export.log','run.log','model.log','report-raw.json','report-export.log','steps.json')){
 $path=Join-Path $run $name
 if(!(Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -le 4){throw "missing raw artifact: $name"}
 $raw[$name]=[ordered]@{bytes=(Get-Item -LiteralPath $path).Length;sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
}
[ordered]@{schema='simlox-a03-closure/v1';case_id='A03';run_id=$RunId;input_sha256=$InputSha256;raw=$raw}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
& $python (Join-Path $case 'validate.py') $run | Set-Content -LiteralPath (Join-Path $run 'validation.json') -Encoding UTF8
if($LASTEXITCODE -ne 0){throw 'A03 CLI assertions failed; preserve raw artifacts'}
& $python (Join-Path $case 'validate_strict.py') $run | Set-Content -LiteralPath (Join-Path $run 'strict-validation.json') -Encoding UTF8
if($LASTEXITCODE -ne 0){throw 'A03 strict summary assertions failed; preserve raw artifacts'}
[ordered]@{schema='simlox-a03-run-manifest/v1';case_id='A03';run_id=$RunId;input_sha256=$InputSha256;closure_sha256=(Get-FileHash (Join-Path $run 'closure.json') -Algorithm SHA256).Hash.ToLowerInvariant();validation_sha256=(Get-FileHash (Join-Path $run 'validation.json') -Algorithm SHA256).Hash.ToLowerInvariant();strict_validation_sha256=(Get-FileHash (Join-Path $run 'strict-validation.json') -Algorithm SHA256).Hash.ToLowerInvariant();strict_validator_sha256=$invocation.strict_validator_sha256;execution_mode='ssh_cli_v1';acceptance_scope='isolated_contract_cli';publication_state='not_published';prerequisites_state='not_all_published';gui_status='not_run'}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $run 'run-manifest.json') -Encoding UTF8
$steps|Format-Table name,exit_code,wall_seconds -AutoSize
} finally {
 if($queueAcquired){$queueMutex.ReleaseMutex()|Out-Null}
 $queueMutex.Dispose()
}

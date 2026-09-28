param(
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$InputSha256
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
if(Get-Process Simlox -ErrorAction SilentlyContinue){throw 'SIMLOX already active; preserve the user session'}
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
 if(Get-Process Simlox -ErrorAction SilentlyContinue){throw 'SIMLOX appeared during serial queue item'}
 $watch=[Diagnostics.Stopwatch]::StartNew()
 $startedUtc=(Get-Date).ToUniversalTime().ToString('o')
 $process=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -PassThru -Wait
 $watch.Stop()
 $completedUtc=(Get-Date).ToUniversalTime().ToString('o')
 $steps += [pscustomobject]@{name=$command.name;arguments=$command.args;exit_code=$process.ExitCode;wall_seconds=$watch.Elapsed.TotalSeconds;started_utc=$startedUtc;completed_utc=$completedUtc}
 $steps|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
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

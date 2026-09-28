param(
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
 [switch]$AllowExistingGui
)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$contractPath=Join-Path $case 'contract.json'
$contract=Get-Content -LiteralPath $contractPath -Raw | ConvertFrom-Json
if($contract.case_id -ne 'A09' -or $contract.version -ne '1.0.0-candidate'){throw 'A09 contract identity changed'}
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$exeSha256='fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$python='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\py312-venv\Scripts\python.exe'
$pythonSha256='2204195cec25879507d958a8b6949add67091244b8b4da9cf3672f993548fa49'
$parser=Join-Path (Join-Path (Split-Path $case -Parent) 'tools') 'validate_native.py'
$parserBinding=Join-Path (Join-Path (Split-Path $case -Parent) 'tools') 'native_binding.py'
$queueMutexName='Global\SimloxIssue18NativeQueue'
$base=Join-Path $case 'runs'
$flatRun=Join-Path $base ($RunId+'-flat')
$nestedRun=Join-Path $base ($RunId+'-nested')
if((Test-Path -LiteralPath $flatRun) -or (Test-Path -LiteralPath $nestedRun)){throw 'immutable A09 run directory already exists'}
if(-not [bool]$env:SSH_CONNECTION){throw 'native CLI runner requires SSH_CONNECTION'}
$executionSessionId=(Get-Process -Id $PID).SessionId
if($executionSessionId -ne 0 -or $env:SESSIONNAME){throw 'native CLI runner requires session-0 SSH'}
$sshAncestors=@()
$ancestorPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++){
 $ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
 if(-not $ancestor){break}
 $sshAncestors += $ancestor.Name
 $ancestorPid=$ancestor.ParentProcessId
}
if($sshAncestors -notcontains 'sshd.exe'){throw 'cannot verify sshd ancestor'}
if(!(Test-Path -LiteralPath $workingDirectory) -or !(Test-Path -LiteralPath $python) -or !(Test-Path -LiteralPath $parser) -or !(Test-Path -LiteralPath $parserBinding)){throw 'known native runtime dependency absent'}
if((Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pythonSha256){throw 'Python validator executable fingerprint changed'}
if(!(Test-Path -LiteralPath $exe) -or (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $exeSha256){throw 'SIMLOX executable fingerprint changed'}
$inputs=@{
 flat=@{path=(Join-Path $case 'native-flat.json');sha=$contract.candidate_input_sha256.flat}
 nested=@{path=(Join-Path $case 'native-nested.json');sha=$contract.candidate_input_sha256.nested}
}
foreach($variant in @('flat','nested')){
 if((Get-FileHash -LiteralPath $inputs[$variant].path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $inputs[$variant].sha){throw "checked $variant input fingerprint changed"}
}
& $python (Join-Path $case 'build.py') --check | Out-Null
if($LASTEXITCODE -ne 0){throw 'A09 pinned-source builder check failed'}
& $python (Join-Path $case 'validate.py') | Out-Null
if($LASTEXITCODE -ne 0){throw 'A09 local static validation failed'}

$queueMutex=New-Object System.Threading.Mutex($false,$queueMutexName)
$queueAcquired=$false
try {
 try {$queueAcquired=$queueMutex.WaitOne(0)}
 catch [System.Threading.AbandonedMutexException] {$queueAcquired=$true}
 if(-not $queueAcquired){throw 'another Issue #18 native runner holds the host-wide queue mutex'}
 $existing=@(Get-Process Simlox -ErrorAction SilentlyContinue)
 $coexistingGui=$null
 if($existing.Count -gt 0){
  if(-not $AllowExistingGui -or $existing.Count -ne 1){throw 'explicit single-GUI coexistence is required'}
  $gui=$existing[0]
  if($gui.SessionId -le 0){throw 'existing SIMLOX is not an interactive GUI'}
  $sessionRows=@(qwinsta 2>&1)
  if($LASTEXITCODE -ne 0){throw 'cannot verify GUI session'}
  $active=@($sessionRows | Where-Object {$_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$gui.SessionId+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)')})
  if($active.Count -ne 1){throw 'existing GUI session is not active'}
  $coexistingGui=[ordered]@{pid=$gui.Id;session_id=$gui.SessionId;session_query_line=$active[0].Trim();process_start_utc=$gui.StartTime.ToUniversalTime().ToString('o')}
 }elseif($AllowExistingGui){throw 'AllowExistingGui specified without an existing GUI'}

 function Assert-ProcessSet {
  $present=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($coexistingGui){
   if($present.Count -ne 1 -or $present[0].Id -ne $coexistingGui.pid -or $present[0].SessionId -ne $coexistingGui.session_id -or $present[0].StartTime.ToUniversalTime().ToString('o') -ne $coexistingGui.process_start_utc){throw 'existing GUI PID/session/process start changed'}
   $sessions=@(qwinsta 2>&1)
   if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {$_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$coexistingGui.session_id+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)')}).Count -ne 1){throw 'existing GUI session is no longer active'}
  }elseif($present.Count -ne 0){throw 'unexpected SIMLOX process appeared'}
 }

 New-Item -ItemType Directory -Path $base -Force | Out-Null
 foreach($variant in @('flat','nested')){
  Assert-ProcessSet
  if((Get-FileHash -LiteralPath $inputs[$variant].path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $inputs[$variant].sha){throw "$variant checked input changed before native run"}
  $run=if($variant -eq 'flat'){$flatRun}else{$nestedRun}
  New-Item -ItemType Directory -Path $run | Out-Null
  Copy-Item -LiteralPath $inputs[$variant].path -Destination (Join-Path $run 'input.json')
  $inputSha=$inputs[$variant].sha
  $source=Join-Path $run 'input.json';$sxi=Join-Path $run 'model.sxi';$sxo=Join-Path $run 'model.sxo'
  if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $inputSha){throw "$variant copied input fingerprint differs"}
  $round=Join-Path $run 'roundtrip-raw.json';$report=Join-Path $run 'report-raw.json'
  $invocation=[ordered]@{
   schema='simlox-a09-invocation/ssh-cli-v1';case_id='A09';case_version='1.0.0-candidate'
   variant=$variant;group_run_id=$RunId;run_id=(Split-Path $run -Leaf)
   created_utc=(Get-Date).ToUniversalTime().ToString('o');original_run_dir=$run;host_name=$env:COMPUTERNAME
   input_sha256=$inputSha;flat_input_sha256=$inputs.flat.sha;nested_input_sha256=$inputs.nested.sha
   contract_sha256=(Get-FileHash $contractPath -Algorithm SHA256).Hash.ToLowerInvariant()
   parameters_sha256=(Get-FileHash (Join-Path $case 'parameters.json') -Algorithm SHA256).Hash.ToLowerInvariant()
   parent_input_sha256=(Get-FileHash (Join-Path (Split-Path $case -Parent) 'A02-single-aircraft-repeated-missions\native-input.json') -Algorithm SHA256).Hash.ToLowerInvariant()
   static_validator_sha256=(Get-FileHash (Join-Path $case 'validate.py') -Algorithm SHA256).Hash.ToLowerInvariant()
   native_validator_sha256=(Get-FileHash (Join-Path $case 'validate_native_cli.py') -Algorithm SHA256).Hash.ToLowerInvariant()
   builder_sha256=(Get-FileHash (Join-Path $case 'build.py') -Algorithm SHA256).Hash.ToLowerInvariant()
   shared_parser_sha256=(Get-FileHash $parser -Algorithm SHA256).Hash.ToLowerInvariant()
   shared_binding_sha256=(Get-FileHash $parserBinding -Algorithm SHA256).Hash.ToLowerInvariant()
   runner_sha256=(Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
   simlox_exe_sha256=$exeSha256;python_exe_sha256=$pythonSha256
   working_directory=$workingDirectory;python_path=$python
   execution_mode='ssh_cli_v1';session_name=$env:SESSIONNAME;session_id=$executionSessionId
   ssh_connection_present=[bool]$env:SSH_CONNECTION;ssh_client_present=[bool]$env:SSH_CLIENT
   ssh_ancestor_names=$sshAncestors;allow_existing_gui=[bool]$AllowExistingGui;coexisting_gui=$coexistingGui
   queue_mutex=$queueMutexName
  }
  $invocation|ConvertTo-Json -Depth 6|Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $commands=@(
   [pscustomobject]@{name='import';args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $source,$sxi,(Join-Path $run 'import.log'))},
   [pscustomobject]@{name='export';args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,$round,(Join-Path $run 'export.log'))},
   [pscustomobject]@{name='calc';args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log'))},
   [pscustomobject]@{name='jsonreport';args=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,$report,(Join-Path $run 'report-export.log'))}
  )
  $steps=@()
  foreach($command in $commands){
   Assert-ProcessSet
   $watch=[Diagnostics.Stopwatch]::StartNew();$startedUtc=(Get-Date).ToUniversalTime().ToString('o')
   $process=$null;$launchError=$null
   try {$process=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait}
   catch {$launchError=$_.Exception.ToString()}
   $watch.Stop();$completedUtc=(Get-Date).ToUniversalTime().ToString('o')
   $guiCheckError=$null
   try {Assert-ProcessSet}
   catch {$guiCheckError=$_.Exception.ToString()}
   $exitCode=if($process){$process.ExitCode}else{$null}
   $steps += [pscustomobject]@{name=$command.name;arguments=$command.args;exit_code=$exitCode;wall_seconds=$watch.Elapsed.TotalSeconds;started_utc=$startedUtc;completed_utc=$completedUtc;launch_error=$launchError;gui_state_check_passed=($null -eq $guiCheckError);gui_state_check_error=$guiCheckError;coexisting_gui_present_after=[bool]($coexistingGui -and $null -eq $guiCheckError)}
   $steps|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
   if($launchError){throw "$variant $($command.name) launch failed after step record: $launchError"}
   if($guiCheckError){throw "$variant $($command.name) GUI state changed after step record: $guiCheckError"}
   if($exitCode -ne 0){throw "$variant $($command.name) exit=$exitCode; preserve raw run"}
   $required= switch($command.name){
    'import' {@('model.sxi','import.log')}
    'export' {@('roundtrip-raw.json','export.log')}
    'calc' {@('model.sxo','run.log','model.log')}
    'jsonreport' {@('report-raw.json','report-export.log')}
   }
   foreach($name in $required){$path=Join-Path $run $name;if(!(Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -le 4){throw "$variant $($command.name) missing/empty $name; preserve raw run"}}
  }
  $raw=@{}
  foreach($name in @('input.json','roundtrip-raw.json','model.sxi','model.sxo','import.log','export.log','run.log','model.log','report-raw.json','report-export.log','steps.json')){
   $path=Join-Path $run $name
   $raw[$name]=[ordered]@{bytes=(Get-Item -LiteralPath $path).Length;sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
  }
  [ordered]@{schema='simlox-a09-closure/v1';case_id='A09';variant=$variant;run_id=(Split-Path $run -Leaf);input_sha256=$inputSha;invocation_sha256=(Get-FileHash (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();raw=$raw}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  & $python (Join-Path $case 'validate_native_cli.py') $run --variant $variant | Set-Content -LiteralPath (Join-Path $run 'validation.json') -Encoding UTF8
  if($LASTEXITCODE -ne 0){throw "$variant native behavior failed; preserve raw run and stop before next candidate"}
  [ordered]@{schema='simlox-a09-run-manifest/v1';case_id='A09';variant=$variant;run_id=(Split-Path $run -Leaf);input_sha256=$inputSha;invocation_sha256=(Get-FileHash (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();closure_sha256=(Get-FileHash (Join-Path $run 'closure.json') -Algorithm SHA256).Hash.ToLowerInvariant();validation_sha256=(Get-FileHash (Join-Path $run 'validation.json') -Algorithm SHA256).Hash.ToLowerInvariant();execution_mode='ssh_cli_v1';scope='isolated_contract_cli_candidate';gui_status='not_run';publication_state='not_published'}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $run 'run-manifest.json') -Encoding UTF8
 }
 Write-Output ([ordered]@{schema='simlox-a09-serial-pair/v1';flat_run=$flatRun;nested_run=$nestedRun;flat_validation_sha256=(Get-FileHash (Join-Path $flatRun 'validation.json') -Algorithm SHA256).Hash.ToLowerInvariant();nested_validation_sha256=(Get-FileHash (Join-Path $nestedRun 'validation.json') -Algorithm SHA256).Hash.ToLowerInvariant();gui_status='not_run';publication_state='not_published'}|ConvertTo-Json -Depth 4)
} finally {
 if($queueAcquired){$queueMutex.ReleaseMutex()|Out-Null}
 $queueMutex.Dispose()
}

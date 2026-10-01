param(
 [Parameter(Mandatory=$true)][ValidateSet('pfac-sum','cycle')][string]$Arm,
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$InputSha256,
 [switch]$AllowExistingGui
)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$contractPath=Join-Path $case 'probe-contract.json'
$diffPath=Join-Path $case 'probe-diff.json'
$input=Join-Path $case ($Arm+'-input.json')
$parentName=if($Arm -eq 'pfac-sum'){'J03-var01-time-two-point-v1.0.0'}else{'J03-var04-nested-time-v1.0.0'}
$parent=Join-Path (Join-Path (Split-Path $case -Parent) $parentName) 'seed-01-input.json'
$dictionary='C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$run=Join-Path (Join-Path $case 'runs') $RunId
if(-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME){throw 'authenticated session-0 SSH required'}
$ancestorNames=@();$ancestorPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $ancestorPid -gt 0;$depth++){
 $ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
 if(-not $ancestor){break}
 $ancestorNames += $ancestor.Name;$ancestorPid=$ancestor.ParentProcessId
}
if($ancestorNames -notcontains 'sshd.exe'){throw 'sshd ancestor missing'}
if(Test-Path -LiteralPath $run){throw 'immutable run directory already exists'}
if($RunId -notmatch ('^j03-{0}-probe-20261001-(01|02)$' -f [regex]::Escape($Arm))){throw 'diagnostic probe ID mismatch'}
if(-not $AllowExistingGui){throw 'explicit GUI coexistence required'}
$contract=Get-Content -LiteralPath $contractPath -Raw | ConvertFrom-Json
$diff=Get-Content -LiteralPath $diffPath -Raw | ConvertFrom-Json
$armContract=$contract.arms.$Arm;$armDiff=$diff.arms.$Arm
if($contract.schema -ne 'simlox-j03-negative-distribution-probe-contract/v1' -or $armContract.input_sha256 -ne $InputSha256 -or $armDiff.input_sha256 -ne $InputSha256){throw 'contract/diff identity mismatch'}
foreach($item in @(
 @($input,$InputSha256),@($parent,$armContract.parent_input_sha256),@($diffPath,$contract.probe_diff_sha256),
 @($dictionary,$contract.dictionary_sha256),@($manual,$contract.manual_sha256),@($exe,$contract.exe_sha256)
)){
 if(!(Test-Path -LiteralPath $item[0]) -or (Get-FileHash -LiteralPath $item[0] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item[1]){throw "source fingerprint differs: $($item[0])"}
}
if(!(Test-Path -LiteralPath $workingDirectory) -or !(Test-Path -LiteralPath $python)){throw 'runtime dependency missing'}
& $python (Join-Path $case 'build.py') --check | Out-Null
if($LASTEXITCODE -ne 0){throw 'builder check failed'}
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue');$acquired=$false
function Seal([string]$state){
 $raw=[ordered]@{}
 foreach($name in @('input.json','roundtrip-raw.json','model.sxi','model.sxo','import.log','export.log','run.log','model.log','steps.json')){
  $path=Join-Path $run $name
  if(Test-Path -LiteralPath $path){$raw[$name]=[ordered]@{bytes=(Get-Item -LiteralPath $path).Length;sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}}
 }
 $sources=[ordered]@{}
 foreach($name in @('probe-contract.json','probe-diff.json','build.py','probe_native_ssh.ps1','pfac-sum-input.json','cycle-input.json')){
  $sources[$name]=(Get-FileHash -LiteralPath (Join-Path $case $name) -Algorithm SHA256).Hash.ToLowerInvariant()
 }
 $sources['parent-input.json']=(Get-FileHash -LiteralPath $parent -Algorithm SHA256).Hash.ToLowerInvariant()
 $sources['database-dictionary.txt']=(Get-FileHash -LiteralPath $dictionary -Algorithm SHA256).Hash.ToLowerInvariant()
 $sources['manual.pdf']=(Get-FileHash -LiteralPath $manual -Algorithm SHA256).Hash.ToLowerInvariant()
 $invocationPath=Join-Path $run 'invocation.json'
 $invocationHash=if(Test-Path -LiteralPath $invocationPath){(Get-FileHash -LiteralPath $invocationPath -Algorithm SHA256).Hash.ToLowerInvariant()}else{$null}
 [ordered]@{schema='simlox-j03-negative-distribution-probe-closure/v1';arm=$Arm;run_id=$RunId;state=$state;input_sha256=$InputSha256;invocation_sha256=$invocationHash;raw=$raw;post_source_sha256=$sources} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
}
try{
 try{$acquired=$queue.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
 if(-not $acquired){throw 'Issue #18 native queue busy'}
 $existing=@(Get-Process Simlox -ErrorAction SilentlyContinue)
 if($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -ne 1 -or -not $existing[0].Responding){throw 'preserved GUI PID 13340 unavailable'}
 $guiStart=$existing[0].StartTime.ToUniversalTime().ToString('o')
 if($guiStart -ne '2026-09-28T10:09:56.8261381Z'){throw 'GUI start identity changed'}
 $sessions=@(qwinsta 2>&1)
 if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {$_ -match ('^\s*>?\s*(?:\S+\s+)?'+[regex]::Escape($env:USERNAME)+'\s+1\s+(?:Active|Disc|\u8fd0\u884c\u4e2d|\u65ad\u5f00)(?:\s|$)')}).Count -ne 1){throw 'GUI session cannot be verified'}
 New-Item -ItemType Directory -Path $run -Force | Out-Null
 Copy-Item -LiteralPath $input -Destination (Join-Path $run 'input.json')
 $source=Join-Path $run 'input.json';$sxi=Join-Path $run 'model.sxi';$sxo=Join-Path $run 'model.sxo';$round=Join-Path $run 'roundtrip-raw.json'
 [ordered]@{schema='simlox-j03-negative-distribution-probe-invocation/ssh-cli-v1';arm=$Arm;run_id=$RunId;input_sha256=$InputSha256;created_utc=(Get-Date).ToUniversalTime().ToString('o');session_id=0;ssh_ancestor_names=$ancestorNames;gui_pid=13340;gui_start_utc=$guiStart;queue_mutex='Global\SimloxIssue18NativeQueue';contract_sha256=(Get-FileHash $contractPath -Algorithm SHA256).Hash.ToLowerInvariant();builder_sha256=(Get-FileHash (Join-Path $case 'build.py') -Algorithm SHA256).Hash.ToLowerInvariant();runner_sha256=(Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
 $commands=@(
  [pscustomobject]@{name='import';args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $source,$sxi,(Join-Path $run 'import.log'))},
  [pscustomobject]@{name='export';args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,$round,(Join-Path $run 'export.log'))},
  [pscustomobject]@{name='calc';args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log'))}
 )
 $steps=@()
 foreach($command in $commands){
  $present=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($present.Count -ne 1 -or $present[0].Id -ne 13340 -or $present[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart){throw 'GUI process set changed before command'}
  $process=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru
  if(-not $process.WaitForExit(60000)){Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue;$process.WaitForExit();throw "native $($command.name) timed out"}
  $after=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  $guiOkay=($after.Count -eq 1 -and $after[0].Id -eq 13340 -and $after[0].StartTime.ToUniversalTime().ToString('o') -eq $guiStart)
  $steps += [pscustomobject]@{name=$command.name;exit_code=$process.ExitCode;coexisting_gui_present_after=[bool]$guiOkay;completed_utc=(Get-Date).ToUniversalTime().ToString('o')}
  $steps | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
  if(-not $guiOkay -or ($command.name -ne 'calc' -and $process.ExitCode -ne 0)){throw "native $($command.name) or GUI guard failed"}
 }
 Seal 'native_steps_complete'
 $steps | Format-Table name,exit_code,coexisting_gui_present_after -AutoSize
}finally{
 try{if((Test-Path -LiteralPath $run) -and -not (Test-Path -LiteralPath (Join-Path $run 'closure.json'))){Seal 'partial_native_probe'}}finally{if($acquired){$queue.ReleaseMutex()|Out-Null};$queue.Dispose()}
}

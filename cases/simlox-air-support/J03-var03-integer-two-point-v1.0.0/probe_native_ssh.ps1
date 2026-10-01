param(
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
 [Parameter(Mandatory=$true)][ValidateRange(1,32)][int]$Seed,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$InputSha256,
 [switch]$AllowExistingGui
)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$contractPath=Join-Path $case 'probe-contract.json'
$diffPath=Join-Path $case 'panel-diff.json'
$inputName=('seed-{0:d2}-input.json' -f $Seed)
$input=Join-Path $case $inputName
$parent=Join-Path (Join-Path (Split-Path $case -Parent) 'J02-determ-boundary-count-v1.0.0') 'determ-2-seed-01-input.json'
$dictionary='C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$exeSha='fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$run=Join-Path (Join-Path $case 'runs') $RunId
if(-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME){throw 'authenticated session-0 SSH required'}
$ancestorNames=@()
$ancestorPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for($depth=0;$depth -lt 8 -and $ancestorPid -gt 0;$depth++){
 $ancestor=Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
 if(-not $ancestor){break}
 $ancestorNames += $ancestor.Name
 $ancestorPid=$ancestor.ParentProcessId
}
if($ancestorNames -notcontains 'sshd.exe'){throw 'sshd ancestor missing'}
if(Test-Path -LiteralPath $run){throw 'immutable run directory already exists'}
if($RunId -notmatch '-probe-'){throw 'diagnostic probe run ID required'}
if(-not $AllowExistingGui){throw 'explicit GUI coexistence required'}
$contract=Get-Content -LiteralPath $contractPath -Raw | ConvertFrom-Json
$diff=Get-Content -LiteralPath $diffPath -Raw | ConvertFrom-Json
if($contract.schema -ne 'simlox-j03-var03-integer-mix-probe-contract/v1' -or $Seed -lt $contract.seed_range_inclusive[0] -or $Seed -gt $contract.seed_range_inclusive[1] -or $diff.input_sha256.$inputName -ne $InputSha256){throw 'contract/diff input identity mismatch'}
foreach($item in @(
 @($input,$InputSha256),@($parent,$contract.parent_input_sha256),
 @($diffPath,$contract.panel_diff_sha256),@($dictionary,$contract.database_dictionary_sha256),
 @($manual,$contract.manual_sha256),@($exe,$exeSha)
)){
 if(!(Test-Path -LiteralPath $item[0]) -or (Get-FileHash -LiteralPath $item[0] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item[1]){throw "source fingerprint differs: $($item[0])"}
}
if(!(Test-Path -LiteralPath $workingDirectory) -or !(Test-Path -LiteralPath $python)){throw 'native runtime dependency missing'}
& $python (Join-Path $case 'build.py') --check | Out-Null
if($LASTEXITCODE -ne 0){throw 'source builder check failed'}
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
$acquired=$false
function Seal([string]$state){
 $raw=[ordered]@{}
 foreach($name in @('input.json','roundtrip-raw.json','model.sxi','model.sxo','import.log','export.log','run.log','model.log','report-raw.json','report-export.log','steps.json')){
  $path=Join-Path $run $name
  if(Test-Path -LiteralPath $path){$raw[$name]=[ordered]@{bytes=(Get-Item -LiteralPath $path).Length;sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}}
 }
 $sources=[ordered]@{}
 foreach($name in @('probe-contract.json','build.py','panel-diff.json','probe_native_ssh.ps1')){
  $path=Join-Path $case $name
  $sources[$name]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
 }
 foreach($seedNumber in 1..32){
  $name=('seed-{0:d2}-input.json' -f $seedNumber)
  $sources[$name]=(Get-FileHash -LiteralPath (Join-Path $case $name) -Algorithm SHA256).Hash.ToLowerInvariant()
 }
 $sources['parent-input.json']=(Get-FileHash -LiteralPath $parent -Algorithm SHA256).Hash.ToLowerInvariant()
 $sources['database-dictionary.txt']=(Get-FileHash -LiteralPath $dictionary -Algorithm SHA256).Hash.ToLowerInvariant()
 $sources['manual.pdf']=(Get-FileHash -LiteralPath $manual -Algorithm SHA256).Hash.ToLowerInvariant()
 $invocationPath=Join-Path $run 'invocation.json'
 $invocationHash=if(Test-Path -LiteralPath $invocationPath){(Get-FileHash -LiteralPath $invocationPath -Algorithm SHA256).Hash.ToLowerInvariant()}else{$null}
 [ordered]@{schema='simlox-j03-var03-integer-mix-probe-closure/v1';seed=$Seed;run_id=$RunId;state=$state;input_sha256=$InputSha256;invocation_sha256=$invocationHash;raw=$raw;post_source_sha256=$sources} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
}
try{
 try{$acquired=$queue.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
 if(-not $acquired){throw 'Issue #18 native queue busy'}
 $existing=@(Get-Process Simlox -ErrorAction SilentlyContinue)
 if($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -ne 1 -or -not $existing[0].Responding){throw 'preserved GUI PID 13340 unavailable'}
 $gui=$existing[0]
 $guiStart=$gui.StartTime.ToUniversalTime().ToString('o')
 if($guiStart -ne '2026-09-28T10:09:56.8261381Z'){throw 'GUI start identity changed'}
 $sessions=@(qwinsta 2>&1)
 if($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {$_ -match ('^\s*>?\s*(?:\S+\s+)?'+[regex]::Escape($env:USERNAME)+'\s+1\s+(?:Active|Disc|\u8fd0\u884c\u4e2d|\u65ad\u5f00)(?:\s|$)')}).Count -ne 1){throw 'GUI session cannot be verified'}
 New-Item -ItemType Directory -Path $run -Force | Out-Null
 Copy-Item -LiteralPath $input -Destination (Join-Path $run 'input.json')
 $source=Join-Path $run 'input.json';$sxi=Join-Path $run 'model.sxi';$sxo=Join-Path $run 'model.sxo';$round=Join-Path $run 'roundtrip-raw.json';$report=Join-Path $run 'report-raw.json'
 [ordered]@{schema='simlox-j03-var03-integer-mix-probe-invocation/ssh-cli-v1';seed=$Seed;run_id=$RunId;input_sha256=$InputSha256;created_utc=(Get-Date).ToUniversalTime().ToString('o');session_id=0;ssh_ancestor_names=$ancestorNames;gui_pid=13340;gui_start_utc=$guiStart;queue_mutex='Global\SimloxIssue18NativeQueue';contract_sha256=(Get-FileHash $contractPath -Algorithm SHA256).Hash.ToLowerInvariant();builder_sha256=(Get-FileHash (Join-Path $case 'build.py') -Algorithm SHA256).Hash.ToLowerInvariant();runner_sha256=(Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
 $commands=@(
  [pscustomobject]@{name='import';args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $source,$sxi,(Join-Path $run 'import.log'))},
  [pscustomobject]@{name='export';args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,$round,(Join-Path $run 'export.log'))},
  [pscustomobject]@{name='calc';args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log'))},
  [pscustomobject]@{name='jsonreport';args=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,$report,(Join-Path $run 'report-export.log'))}
 )
 $steps=@()
 foreach($command in $commands){
  $present=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($present.Count -ne 1 -or $present[0].Id -ne 13340 -or $present[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart){throw 'GUI process set changed before command'}
  $process=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru
  if(-not $process.WaitForExit(120000)){Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue;$process.WaitForExit();throw "native $($command.name) timed out"}
  $after=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  $guiOkay=($after.Count -eq 1 -and $after[0].Id -eq 13340 -and $after[0].StartTime.ToUniversalTime().ToString('o') -eq $guiStart)
  $steps += [pscustomobject]@{name=$command.name;exit_code=$process.ExitCode;coexisting_gui_present_after=[bool]$guiOkay;completed_utc=(Get-Date).ToUniversalTime().ToString('o')}
  $steps | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
  if(-not $guiOkay -or $process.ExitCode -ne 0){throw "native $($command.name) or GUI guard failed"}
  if($command.name -eq 'calc'){
   if(!(Test-Path $sxo) -or (Get-Item $sxo).Length -le 4){throw 'empty simulation output'}
   $conversion=[regex]::Match((Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw),'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
   if(-not $conversion.Success -or [int]$conversion.Groups[1].Value -ne 0){throw 'converter error or missing summary; report export withheld'}
  }
 }
 foreach($name in @('input.json','roundtrip-raw.json','model.sxi','model.sxo','import.log','export.log','run.log','model.log','report-raw.json','report-export.log','steps.json')){
  $path=Join-Path $run $name
  if(!(Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -le 4){throw "missing raw artifact: $name"}
 }
 Seal 'native_steps_complete'
 $steps | Format-Table name,exit_code,coexisting_gui_present_after -AutoSize
}finally{
 try{if((Test-Path -LiteralPath $run) -and -not (Test-Path -LiteralPath (Join-Path $run 'closure.json'))){Seal 'partial_native_probe'}}finally{if($acquired){$queue.ReleaseMutex()|Out-Null};$queue.Dispose()}
}

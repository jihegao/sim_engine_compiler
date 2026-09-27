param(
 [Parameter(Mandatory=$true)][ValidateSet('B01','B02','B03','C01','C02','C03')][string]$CaseId,
 [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')][string]$VariantId,
 [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')][string]$RunId,
 [Parameter(Mandatory=$true)][string]$InputPath,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$InputSha256,
 [switch]$ProbeOnly
)

$ErrorActionPreference='Stop'
$bundle=(Resolve-Path $PSScriptRoot).Path
$repo=(Resolve-Path (Join-Path $bundle '..\..\..')).Path
$input=(Resolve-Path -LiteralPath $InputPath).Path
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$exeSha256='fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$python='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\py312-venv\Scripts\python.exe'
$base=Join-Path $repo ('data\local\simlox-preparation-resource\v1\'+$CaseId+'\'+$VariantId)
$run=Join-Path $base $RunId
$resolved=[IO.Path]::GetFullPath($run)
$allowed=[IO.Path]::GetFullPath($base)+[IO.Path]::DirectorySeparatorChar
if(-not $resolved.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)){throw 'run path escapes bound evidence root'}
if(Test-Path -LiteralPath $run){throw "immutable run directory exists: $run"}
if(!(Test-Path -LiteralPath $workingDirectory)){throw 'known native working directory absent'}
if(!(Test-Path -LiteralPath $exe) -or (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $exeSha256){throw 'SIMLOX executable fingerprint changed'}
if(!(Test-Path -LiteralPath $python)){throw 'isolated Python missing'}
if((Get-FileHash -LiteralPath $input -Algorithm SHA256).Hash.ToLowerInvariant() -ne $InputSha256){throw 'checked source input fingerprint changed'}
if(Get-Process Simlox -ErrorAction SilentlyContinue){throw 'SIMLOX process already running; leave user window untouched'}

New-Item -ItemType Directory -Path $run -Force | Out-Null
Copy-Item -LiteralPath $input -Destination (Join-Path $run 'input.json')
$source=Join-Path $run 'input.json'
$binding=Join-Path $bundle 'binding.py'
$validator=Join-Path $bundle 'validate.py'
$invocationOutput=& $python $binding prepare --run-dir $run --source-input $input --case $CaseId --variant $VariantId --run-id $RunId --input-sha256 $InputSha256
if($LASTEXITCODE -ne 0){throw 'pre-launch invocation binding failed; no native process started'}
$invocation=$invocationOutput|ConvertFrom-Json
if(!$invocation.invocation_id){throw 'pre-launch invocation ID absent'}

$sxi=Join-Path $run 'model.sxi'
$sxo=Join-Path $run 'model.sxo'
$round=Join-Path $run 'roundtrip-raw.json'
$report=Join-Path $run 'report-raw.json'
$commands=@(
 [pscustomobject]@{name='import';args=$invocation.planned_arguments.import},
 [pscustomobject]@{name='export';args=$invocation.planned_arguments.export},
 [pscustomobject]@{name='calc';args=$invocation.planned_arguments.calc},
 [pscustomobject]@{name='jsonreport';args=$invocation.planned_arguments.jsonreport}
)
$records=@()
foreach($command in $commands){
 if(Get-Process Simlox -ErrorAction SilentlyContinue){throw 'SIMLOX process appeared; do not disturb it'}
 $watch=[Diagnostics.Stopwatch]::StartNew()
 $process=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
 $watch.Stop()
 $records += [pscustomobject]@{
  name=$command.name
  invocation_id=$invocation.invocation_id
  executable=$exe
  arguments=$command.args
  working_directory=$workingDirectory
  exit_code=$process.ExitCode
  wall_seconds=$watch.Elapsed.TotalSeconds
 }
 $records|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
 if($process.ExitCode -ne 0){throw "$CaseId/$VariantId/$RunId/$($command.name) exit $($process.ExitCode)"}
 if($command.name -eq 'import' -and (!(Test-Path $sxi) -or (Get-Item $sxi).Length -le 4)){throw 'exit 0 without a valid SXI'}
 if($command.name -eq 'export'){
  if(!(Test-Path $round) -or (Get-Item $round).Length -le 4){throw 'exit 0 without a valid exported JSON'}
  & $python $binding roundtrip --run-dir $run
  if($LASTEXITCODE -ne 0){throw 'nonempty business rows changed during native roundtrip; calc was not started'}
 }
 if($command.name -eq 'calc'){
  if(!(Test-Path $sxo) -or (Get-Item $sxo).Length -le 4){throw 'exit 0 with absent/4-byte SXO'}
  $log=Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw
  $summary=[regex]::Match($log,'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
  if(!$summary.Success -or [int]$summary.Groups[1].Value -ne 0){throw 'native conversion errors or missing conversion summary'}
  if(!(Test-Path (Join-Path $run 'model.log')) -or (Get-Item (Join-Path $run 'model.log')).Length -le 4){throw 'ENLOG first-repetition event log absent'}
 }
 if($command.name -eq 'jsonreport' -and (!(Test-Path $report) -or (Get-Item $report).Length -le 4)){throw 'exit 0 without a valid report'}
}

$closureOutput=& $python $binding seal --run-dir $run
if($LASTEXITCODE -ne 0){throw 'post-run raw artifact closure failed; preserve native files'}
$closure=$closureOutput|ConvertFrom-Json
if($closure.invocation_id -ne $invocation.invocation_id){throw 'closure invocation ID mismatch'}

if($ProbeOnly){
 $verifyOutput=& $python $binding verify --run-dir $run --case $CaseId --variant $VariantId
 if($LASTEXITCODE -ne 0){throw 'sealed probe binding verification failed'}
 $verified=$verifyOutput|ConvertFrom-Json
 $probe=[ordered]@{
  schema_version='simlox-preparation-resource-probe-manifest/v1'
  task_id='simlox-preparation-resource-v1'
  case_id=$CaseId
  variant_id=$VariantId
  run_id=$RunId
  invocation_id=$invocation.invocation_id
  input_sha256=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
  simlox_exe_sha256=$exeSha256
  invocation_sha256=$verified.invocation_sha256
  closure_sha256=$verified.closure_sha256
  status='sealed_probe_behavior_unverified'
  purpose='calibrate native ENLOG and report syntax before the strict validator is frozen'
  validator_executed=$false
  gui_status='not_run'
  cross_engine_status='not_run'
 }
 $probe|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $run 'probe-manifest.json') -Encoding UTF8
 $records|Format-Table name,exit_code,wall_seconds -AutoSize
 return
}

& $python $validator --run-dir $run --case $CaseId --variant $VariantId
if($LASTEXITCODE -ne 0){throw 'native artifacts exist but behavior acceptance failed; preserve immutable run directory'}
$validation=Join-Path $run 'validation.json'
$normalized=Join-Path $run 'report-normalized.json'
if(!(Test-Path $validation) -or (Get-Item $validation).Length -le 4){throw 'validator returned success without validation.json'}
if(!(Test-Path $normalized) -or (Get-Item $normalized).Length -le 4){throw 'validator returned success without report-normalized.json'}

$manifest=[ordered]@{
 schema_version='simlox-preparation-resource-run-manifest/v1'
 task_id='simlox-preparation-resource-v1'
 case_id=$CaseId
 variant_id=$VariantId
 run_id=$RunId
 invocation_id=$invocation.invocation_id
 input_sha256=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
 simlox_exe_sha256=$exeSha256
 invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant()
 closure_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'closure.json') -Algorithm SHA256).Hash.ToLowerInvariant()
 validation_sha256=(Get-FileHash -LiteralPath $validation -Algorithm SHA256).Hash.ToLowerInvariant()
 normalized_report_sha256=(Get-FileHash -LiteralPath $normalized -Algorithm SHA256).Hash.ToLowerInvariant()
 status='cli_behavior_verified'
 acceptance_scope='isolated_contract_cli'
 publication_state='not_published'
 prerequisites_state='not_all_published'
 gui_status='not_run'
 cross_engine_status='not_run'
}
$manifest|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $run 'run-manifest.json') -Encoding UTF8
$records|Format-Table name,exit_code,wall_seconds -AutoSize

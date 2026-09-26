param(
 [Parameter(Mandatory=$true)][ValidateSet('before_launch','in_flight','before_completion','printed_tie','after_completion')][string]$Variant,
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$InputSha256
)
$ErrorActionPreference='Stop'
$library=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$repo=(Resolve-Path (Join-Path $library '..\..')).Path
$input=Join-Path $repo ('data\local\simlox-case-library\v1\collection-inputs\'+$Variant+'.json')
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$exeSha256='fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$python='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\py312-venv\Scripts\python.exe'
$base=Join-Path $repo 'data\local\simlox-case-library\v1\collection-runs'
$run=Join-Path $base $RunId
$resolved=[IO.Path]::GetFullPath($run)
$allowed=[IO.Path]::GetFullPath($base)+[IO.Path]::DirectorySeparatorChar
if(-not $resolved.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)){throw 'run path escapes ignored evidence root'}
if(Test-Path -LiteralPath $run){throw "immutable run directory exists: $run"}
if(!(Test-Path -LiteralPath $workingDirectory)){throw 'known native working directory absent'}
if(!(Test-Path -LiteralPath $exe) -or (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $exeSha256){throw 'SIMLOX executable fingerprint changed'}
if(!(Test-Path -LiteralPath $python)){throw 'isolated Python missing'}
if((Get-FileHash -LiteralPath $input -Algorithm SHA256).Hash.ToLowerInvariant() -ne $InputSha256){throw 'variant input fingerprint changed'}
if(Get-Process Simlox -ErrorAction SilentlyContinue){throw 'SIMLOX process already running; leave user window untouched'}
New-Item -ItemType Directory -Path $run -Force | Out-Null
Copy-Item -LiteralPath $input -Destination (Join-Path $run 'input.json')
$source=Join-Path $run 'input.json'
$sxi=Join-Path $run 'model.sxi'
$sxo=Join-Path $run 'model.sxo'
$round=Join-Path $run 'roundtrip-raw.json'
$report=Join-Path $run 'report-raw.json'
$commands=@(
 [pscustomobject]@{name='import';args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $source,$sxi,(Join-Path $run 'import.log'))},
 [pscustomobject]@{name='export';args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,$round,(Join-Path $run 'export.log'))},
 [pscustomobject]@{name='calc';args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log'))},
 [pscustomobject]@{name='jsonreport';args=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,$report,(Join-Path $run 'report-export.log'))}
)
$records=@()
foreach($command in $commands){
 if(Get-Process Simlox -ErrorAction SilentlyContinue){throw 'SIMLOX process appeared; do not disturb it'}
 $watch=[Diagnostics.Stopwatch]::StartNew()
 $process=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
 $watch.Stop()
 $records += [pscustomobject]@{name=$command.name;executable=$exe;arguments=$command.args;working_directory=$workingDirectory;exit_code=$process.ExitCode;wall_seconds=$watch.Elapsed.TotalSeconds}
 $records|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
 if($process.ExitCode -ne 0){throw "$Variant/$RunId/$($command.name) exit $($process.ExitCode)"}
 if($command.name -eq 'import' -and (!(Test-Path $sxi) -or (Get-Item $sxi).Length -le 4)){throw 'exit 0 without a valid SXI'}
 if($command.name -eq 'export'){
  if(!(Test-Path $round) -or (Get-Item $round).Length -le 4){throw 'exit 0 without a valid exported JSON'}
  & $python (Join-Path $PSScriptRoot 'check_roundtrip.py') $source $round (Join-Path $run 'roundtrip-check.json')
  if($LASTEXITCODE -ne 0){throw 'nonempty business rows changed during native roundtrip'}
 }
 if($command.name -eq 'calc'){
  if(!(Test-Path $sxo) -or (Get-Item $sxo).Length -le 4){throw 'exit 0 with absent/4-byte SXO'}
  $log=Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw -Encoding UTF8
  $summary=[regex]::Match($log,'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
  if(!$summary.Success -or [int]$summary.Groups[1].Value -ne 0){throw 'native conversion errors or missing conversion summary'}
  if(!(Test-Path (Join-Path $run 'model.log'))){throw 'ENLOG first-repetition event log absent'}
 }
 if($command.name -eq 'jsonreport' -and (!(Test-Path $report) -or (Get-Item $report).Length -le 4)){throw 'exit 0 without a valid report'}
}
& $python (Join-Path $PSScriptRoot 'validate_collection.py') --run-dir $run --variant $Variant
if($LASTEXITCODE -ne 0){throw 'horizon probe evidence invalid; preserve run directory'}
[pscustomobject]@{task_id='simlox-case-library-a01-a02-v1';variant=$Variant;run_id=$RunId;input_sha256=$InputSha256;simlox_exe_sha256=$exeSha256;validation_path=(Join-Path $run 'validation.json');status='native_probe_recorded'}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $run 'run-manifest.json') -Encoding UTF8
$records|Format-Table name,exit_code,wall_seconds -AutoSize

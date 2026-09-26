param([Parameter(Mandatory=$true)][string]$Stem)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$base=Join-Path $repo 'data\local\j35-contract-probes'
$dir=Join-Path $base $Stem
$full=[IO.Path]::GetFullPath($dir)
$allowed=[IO.Path]::GetFullPath($base)+[IO.Path]::DirectorySeparatorChar
if(-not $full.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)){throw 'Probe path escapes data/local/j35-contract-probes'}
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$nativeWorkingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$expected='fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
if((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected){throw 'SIMLOX binary fingerprint changed'}
$input=Join-Path $dir ($Stem+'.json')
$manifest=Get-Content -LiteralPath (Join-Path $dir 'provenance.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if((Get-FileHash -LiteralPath $input -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.input_sha256){throw 'Input fingerprint changed'}
if(Get-Process Simlox -ErrorAction SilentlyContinue){throw 'SIMLOX process already running; leave it untouched'}
$sxi=Join-Path $dir ($Stem+'.sxi')
$sxo=Join-Path $dir ($Stem+'.sxo')
$round=Join-Path $dir ($Stem+'-roundtrip.json')
$report=Join-Path $dir ($Stem+'-report-raw.json')
foreach($path in @($sxi,$sxo,$round,$report,(Join-Path $dir ($Stem+'.log')))){
 if(Test-Path -LiteralPath $path){throw "Output exists; refusing overwrite: $path"}
}
$steps=@(
 [pscustomobject]@{name='import';args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $input,$sxi,(Join-Path $dir 'import.log'))},
 [pscustomobject]@{name='export';args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,$round,(Join-Path $dir 'export.log'))},
 [pscustomobject]@{name='calc';args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $dir 'run.log'))}
)
$records=@()
foreach($step in $steps){
 if(Get-Process Simlox -ErrorAction SilentlyContinue){throw 'SIMLOX process appeared; leave it untouched'}
 $watch=[Diagnostics.Stopwatch]::StartNew()
 $proc=Start-Process -FilePath $exe -ArgumentList $step.args -WorkingDirectory $nativeWorkingDirectory -WindowStyle Hidden -PassThru -Wait
 $watch.Stop()
 $records += [pscustomobject]@{name=$step.name;executable=$exe;arguments=$step.args;exit_code=$proc.ExitCode;wall_seconds=$watch.Elapsed.TotalSeconds}
 $records|ConvertTo-Json -Depth 6|Set-Content -LiteralPath (Join-Path $dir 'steps.json') -Encoding UTF8
 if($proc.ExitCode -ne 0){throw "$Stem/$($step.name) exit $($proc.ExitCode)"}
 if($step.name -eq 'import' -and (!(Test-Path $sxi) -or (Get-Item $sxi).Length -le 4)){throw "$Stem import returned exit 0 without a valid SXI; see import.log"}
 if($step.name -eq 'export' -and (!(Test-Path $round) -or (Get-Item $round).Length -le 4)){throw "$Stem export returned exit 0 without a JSON model; see export.log"}
 if($step.name -eq 'export'){
  $python='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\py312-venv\Scripts\python.exe'
  & $python (Join-Path $PSScriptRoot 'verify_native_roundtrip.py') $input $round (Join-Path $dir 'roundtrip-check.json')
  if($LASTEXITCODE -ne 0){throw "$Stem nonempty business rows changed during import/export"}
 }
}
$run=Get-Content -LiteralPath (Join-Path $dir 'run.log') -Raw
if([string]::IsNullOrWhiteSpace($run)){throw "$Stem calc returned exit 0 but run.log is empty"}
$m=[regex]::Match($run,'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
if(!$m.Success){throw 'Missing conversion summary'}
$size=if(Test-Path $sxo){(Get-Item $sxo).Length}else{0}
$valid=([int]$m.Groups[1].Value -eq 0) -and ($size -gt 4)
[pscustomobject]@{conversion_errors=[int]$m.Groups[1].Value;conversion_warnings=[int]$m.Groups[2].Value;conversion_notes=[int]$m.Groups[3].Value;sxo_bytes=$size;valid=$valid}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $dir 'validity.json') -Encoding UTF8
if(!$valid){throw "$Stem invalid conversion or 4-byte SXO"}
if(Get-Process Simlox -ErrorAction SilentlyContinue){throw 'SIMLOX process appeared; leave it untouched'}
$args='"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,$report,(Join-Path $dir 'report-export.log')
$watch=[Diagnostics.Stopwatch]::StartNew()
$proc=Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $nativeWorkingDirectory -WindowStyle Hidden -PassThru -Wait
$watch.Stop()
$records += [pscustomobject]@{name='jsonreport';executable=$exe;arguments=$args;exit_code=$proc.ExitCode;wall_seconds=$watch.Elapsed.TotalSeconds}
$records|ConvertTo-Json -Depth 6|Set-Content -LiteralPath (Join-Path $dir 'steps.json') -Encoding UTF8
if($proc.ExitCode -ne 0 -or !(Test-Path $report)){throw 'Report export failed'}
$records|Format-Table name,exit_code,wall_seconds -AutoSize

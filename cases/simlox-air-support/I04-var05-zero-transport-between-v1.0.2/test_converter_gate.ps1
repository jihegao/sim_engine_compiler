$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$runner=Get-Content -LiteralPath (Join-Path $case 'run_native_ssh.ps1') -Raw -Encoding UTF8
$start=$runner.IndexOf('function Assert-ConverterLog(')
$end=$runner.IndexOf('function Save-Steps(', $start)
if ($start -lt 0 -or $end -le $start) { throw 'runner converter function not found' }
Invoke-Expression $runner.Substring($start,$end-$start)
function Get-Sha([string]$path) {
  $stream=[System.IO.File]::OpenRead($path)
  $hasher=[System.Security.Cryptography.SHA256]::Create()
  try { return ([BitConverter]::ToString($hasher.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
  finally { $stream.Dispose();$hasher.Dispose() }
}
$parent=Join-Path (Split-Path $case -Parent) 'I04-var01-system-between-v1.0.0\runs\i04-var01-system-between-v100-ssh-20261005-01\between-run.log'
$oldRun=Split-Path $parent -Parent
$proof=Join-Path $case ('test-output\converter-pure-'+(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffffffZ')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $proof -Force | Out-Null
$text=Get-Content -LiteralPath $parent -Raw -Encoding UTF8
$text=$text.Replace($oldRun.Replace('\','/'),$proof.Replace('\','/')).Replace($oldRun,$proof)
$text=$text.Replace('between.sxi','model.sxi').Replace('between.sxo','model.sxo')
$log=Join-Path $proof 'model-run.log'
Set-Content -LiteralPath $log -Value $text -Encoding UTF8 -NoNewline
Assert-ConverterLog $proof (Get-Sha $log)
$modified=$text.Replace('Input data conversion time:', "Warning: unnumbered extra diagnostic`r`nInput data conversion time:")
Set-Content -LiteralPath $log -Value $modified -Encoding UTF8 -NoNewline
$rejected=$false
try { Assert-ConverterLog $proof (Get-Sha $log) } catch { $rejected=$true }
if (-not $rejected) { throw 'extra unnumbered diagnostic escaped' }
$failedRun=Join-Path (Split-Path $case -Parent) 'I04-var05-zero-transport-between-v1.0.0\runs\i04-var05-zero-transport-between-v100-ssh-20261008-01'
$failedLog=Join-Path $failedRun 'model-run.log'
if (-not (Test-Path -LiteralPath $failedLog -PathType Leaf)) { throw 'sealed v100 converter negative absent' }
$failedRejected=$false
try { Assert-ConverterLog $failedRun (Get-Sha $failedLog) } catch { $failedRejected=$true }
if (-not $failedRejected) { throw 'sealed corrupt v100 File path escaped' }
[ordered]@{schema='i04-var05-converter-pure-test/v102';positive=$true;
  extra_unnumbered_diagnostic_rejected=$true;sealed_v100_corrupt_file_rejected=$true;
  native_calls=0} | ConvertTo-Json -Compress

$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$repo=(Resolve-Path (Join-Path $case '..\..\..')).Path
$runner=Get-Content -LiteralPath (Join-Path $case 'run_native_ssh.ps1') -Raw -Encoding UTF8
$start=$runner.IndexOf('function Assert-ConverterLog(')
$end=$runner.IndexOf('function Save-Steps(', $start)
if ($start -lt 0 -or $end -le $start) { throw 'runner converter function absent' }
Invoke-Expression $runner.Substring($start,$end-$start)
function Get-Sha([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Must-Reject([scriptblock]$script,[string]$label) {
  $didReject=$false
  try { & $script } catch { $didReject=$true }
  if (-not $didReject) { throw "private negative escaped: $label" }
}
function Write-Clone([string]$path,[string]$body) {
  [System.IO.File]::WriteAllBytes($path,[System.Text.UTF8Encoding]::new($false).GetBytes($body))
}
$parent=Join-Path $repo 'cases\simlox-air-support\E05-local-repair-reissue-v1.0.0\runs\e05-v100-ssh-20260929-01\run.log'
if ((Get-Item -LiteralPath $parent).Length -ne 929 -or
    (Get-Sha $parent) -cne '922d6c97cc6f45cca7f1a8a5eadd6254bf4e542b8f032c1a5273c8bd4d7f6f43') {
  throw 'accepted E05 one-warning converter witness changed'
}
$oldRun=Split-Path -Parent $parent
$nativeRunDirectory='C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\tmp\i05-var04-native-v103-20261009-01'
$proofRoot=Join-Path $repo 'tmp\pure-proofs'
$stem='i05v04-t101-'+[Guid]::NewGuid().ToString('N').Substring(0,8)
$padding=$nativeRunDirectory.Length-($proofRoot.Length+1+$stem.Length)
if ($padding -lt 0) { throw 'unique proof path cannot match native path length' }
$proof=Join-Path $proofRoot ($stem+('x'*$padding))
if (Test-Path -LiteralPath $proof) { throw 'unique proof path already exists' }
$cursor=[System.IO.Path]::GetPathRoot($proof)
foreach($part in $proof.Substring($cursor.Length).Split([System.IO.Path]::DirectorySeparatorChar)) {
  if ($part -eq '') { continue }
  $cursor=Join-Path $cursor $part
  if (Test-Path -LiteralPath $cursor) {
    if (((Get-Item -LiteralPath $cursor -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
      throw 'proof path reparse ancestor'
    }
  }
}
if ([System.Text.Encoding]::ASCII.GetByteCount('File: '+(Join-Path $proof 'model.sxi').Replace('\','/')) -ne 119) {
  throw 'proof path does not exercise exact 119-byte File line'
}
New-Item -ItemType Directory -Path $proof -Force | Out-Null
$text=Get-Content -LiteralPath $parent -Raw -Encoding UTF8
$text=$text.Replace($oldRun.Replace('\','/'),$proof.Replace('\','/')).Replace($oldRun,$proof)
if ($text.Contains($oldRun) -or $text.Contains($oldRun.Replace('\','/')) -or
    $text -notmatch 'warning #108' -or $text -match 'warning #126') {
  throw 'accepted E05 converter path mutation did not close'
}
$log=Join-Path $proof 'model-run.log'
Write-Clone $log $text
Assert-ConverterLog $proof (Get-Sha $log)
function Reject-Clone([string]$label,[string]$old,[string]$new) {
  if ([regex]::Matches($text,[regex]::Escape($old)).Count -ne 1 -or $old -ceq $new) {
    throw "fixture mutation target is not unique: $label"
  }
  $body=$text.Replace($old,$new)
  if ($body -ceq $text) { throw "fixture did not mutate: $label" }
  Write-Clone $log $body
  Must-Reject { Assert-ConverterLog $proof (Get-Sha $log) } $label
  Copy-Item -LiteralPath $log -Destination (Join-Path $proof ($label+'.log.bytes'))
}
$in=Join-Path $proof 'model.sxi';$out=Join-Path $proof 'model.sxo';$file=$in.Replace('\','/')
Reject-Clone 'forward-input-alias' ('Input file: '+$in) ('Input file: '+$file)
Reject-Clone 'backslash-file-alias' ('File: '+$file) ('File: '+$in)
Reject-Clone 'wrong-file-extension' ('File: '+$file) ('File: '+$file.Replace('.sxi','.sxo'))
Reject-Clone 'wrong-output' ('Output file: '+$out) ('Output file: '+$in)
Reject-Clone 'extra-diagnostic' 'Input data conversion time:' "Station unused: BASE-02`r`nInput data conversion time:"
Reject-Clone 'wrong-warning' 'warning #108' 'warning #126'
Reject-Clone 'wrong-summary' 'Errors: 0, Warnings: 1, Notes: 0' 'Errors: 0, Warnings: 2, Notes: 0'
Write-Clone $log ([char]0xFEFF+$text)
Must-Reject { Assert-ConverterLog $proof (Get-Sha $log) } 'UTF8-BOM'
Copy-Item -LiteralPath $log -Destination (Join-Path $proof 'UTF8-BOM.log.bytes')
if (-not $text.EndsWith("`r`n")) { throw 'positive fixture terminal CRLF absent' }
Write-Clone $log $text.Substring(0,$text.Length-2)
Must-Reject { Assert-ConverterLog $proof (Get-Sha $log) } 'missing-terminal-CRLF'
Copy-Item -LiteralPath $log -Destination (Join-Path $proof 'missing-terminal-CRLF.log.bytes')
. (Join-Path $case 'preflight_receipt.ps1')
$malformedArray=[System.Collections.ArrayList]::new()
try {
  Assert-RunDirectory -value $malformedArray -expected $nativeRunDirectory -field 'array run path'
  throw 'empty-array native_run_directory escaped'
} catch {
  if ($_.Exception.Message -cne 'array run path is not the exact approved native run directory string') {
    throw
  }
}
Must-Reject { Assert-RunDirectory ($nativeRunDirectory+'\..\alias') $nativeRunDirectory 'alias path' } 'aliased native_run_directory'
Must-Reject { Assert-JsonKeys ([pscustomobject]@{}) @('native_run_directory') 'missing path' } 'missing native_run_directory'
Must-Reject { Assert-JsonKeys ([pscustomobject]@{native_run_directory=$nativeRunDirectory;extra=1}) @('native_run_directory') 'extra path key' } 'extra native_run_directory key'
[ordered]@{schema='i05-var04-converter-pure-test/v103';positive=$true;
  negative_clones=9;receipt_schema_negatives=4;file_line_ascii_bytes=119;
  proof_directory=$proof;native_calls=0;accepted_checker_calls=0} | ConvertTo-Json -Compress

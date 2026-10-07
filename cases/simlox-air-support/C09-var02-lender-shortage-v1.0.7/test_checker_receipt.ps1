$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
. (Join-Path $case 'checker_receipt.ps1')
if ($PSVersionTable.PSVersion.Major -ne 5) { throw 'PowerShell 5 checker-receipt test required' }
$dir = Join-Path $env:TEMP ('c09-v107-checker-test-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $dir | Out-Null
$path = Join-Path $dir 'verdict.json'
$runId = 'c09-var02-v107-shortage-ssh-20261007-01'
$inputSha = 'a036c16bbdd28b35047ba8a064722c6a1bde21c036435263dd5713dd710767a4'
$exportSha = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
function Write-Fixture([object]$fixture) { $fixture | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $path -Encoding UTF8 }
function Reject([string]$stage) {
  $failed = $false
  try { Assert-CheckerVerdict $stage $path $runId $inputSha $exportSha | Out-Null } catch { $failed = $true }
  if (-not $failed) { throw "production checker receipt accepted bad $stage JSON" }
}

$roundtrip = [ordered]@{schema='c09-var02-v107-roundtrip/v1';arm='shortage';passed=$true;
  issues=@();authored_row_tables=25;source_sha256=$inputSha;export_sha256=$exportSha}
Write-Fixture $roundtrip
Assert-CheckerVerdict 'check_import_export' $path $runId $inputSha $exportSha | Out-Null
$rejections = 0
foreach ($key in @('schema','arm','passed','issues','authored_row_tables','source_sha256','export_sha256')) {
  $bad=[ordered]@{};foreach($k in $roundtrip.Keys){$bad[$k]=$roundtrip[$k]}
  switch ($key) {
    'schema' {$bad[$key]='wrong'}
    'arm' {$bad[$key]='ordinary'}
    'passed' {$bad[$key]='true'}
    'issues' {$bad[$key]=@('drift')}
    'authored_row_tables' {$bad[$key]='25'}
    'source_sha256' {$bad[$key]='b'*64}
    'export_sha256' {$bad[$key]='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'}
  }
  Write-Fixture $bad;Reject 'check_import_export';$rejections++
}
[System.IO.File]::WriteAllText($path, '{invalid', (New-Object System.Text.UTF8Encoding($false)))
Reject 'check_import_export';$rejections++

$behavior=[ordered]@{schema='c09-var02-v107-author-validation/v1';passed=$true;
  decision='GO_BOUNDED_PROSPECTIVE_CHILD';run_id=$runId;control_report_cells=1754;
  child_report_cells=1754;new_native_runs=1}
Write-Fixture $behavior
Assert-CheckerVerdict 'check_behavior' $path $runId $inputSha $exportSha | Out-Null
foreach ($key in @('schema','passed','decision','run_id','control_report_cells','child_report_cells','new_native_runs')) {
  $bad=[ordered]@{};foreach($k in $behavior.Keys){$bad[$k]=$behavior[$k]}
  switch ($key) {
    'schema' {$bad[$key]='wrong'}
    'passed' {$bad[$key]=$false}
    'decision' {$bad[$key]='NO_GO'}
    'run_id' {$bad[$key]='wrong'}
    'control_report_cells' {$bad[$key]='1754'}
    'child_report_cells' {$bad[$key]=1753}
    'new_native_runs' {$bad[$key]=0}
  }
  Write-Fixture $bad;Reject 'check_behavior';$rejections++
}
Write-Fixture $behavior
Reject 'unknown_checker';$rejections++
[ordered]@{schema='c09-var02-v107-checker-receipt-static-test/v1';passed=$true;
  positives=2;rejections=$rejections;native_process_started=$false} | ConvertTo-Json -Compress

$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'checker_receipt.ps1')
if ($PSVersionTable.PSVersion.Major -ne 5) { throw 'PS5 checker-receipt test required' }
$dir=Join-Path $env:TEMP ('c02-v101-checker-test-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $dir | Out-Null
$path=Join-Path $dir 'verdict.json'
$runId='c02-var01-v101-personnel0-ssh-20261007-01'
$inputSha='bab34055ae4f2ee3efac4fa9cb8f545ba2355daad0751a7d5508947f17d3cec2'
$exportSha='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
function Write-Fixture([object]$data) { $data|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $path -Encoding UTF8 }
function Reject([string]$stage) {
  $failed=$false
  try { Assert-CheckerVerdict $stage $path $runId $inputSha $exportSha|Out-Null } catch { $failed=$true }
  if (-not $failed) { throw "bad $stage JSON was accepted" }
}
$roundtrip=[ordered]@{schema='c02-var01-v101-roundtrip/v1';passed=$true;issues=@();
  authored_row_tables=20;input_sha256=$inputSha;export_sha256=$exportSha}
Write-Fixture $roundtrip
Assert-CheckerVerdict 'check_import_export' $path $runId $inputSha $exportSha|Out-Null
$rejections=0
foreach($field in @('schema','passed','issues','authored_row_tables','input_sha256','export_sha256')) {
  $bad=[ordered]@{};foreach($key in $roundtrip.Keys){$bad[$key]=$roundtrip[$key]}
  switch($field) {
    'schema'{$bad[$field]='wrong'} 'passed'{$bad[$field]='true'}
    'issues'{$bad[$field]=@('drift')} 'authored_row_tables'{$bad[$field]='20'}
    'input_sha256'{$bad[$field]='b'*64} 'export_sha256'{$bad[$field]='b'*64}
  }
  Write-Fixture $bad;Reject 'check_import_export';$rejections++
}
[IO.File]::WriteAllText($path,'{invalid',[Text.UTF8Encoding]::new($false))
Reject 'check_import_export';$rejections++
$behavior=[ordered]@{schema='c02-var01-v101-behavior/v1';passed=$true;run_id=$runId;
  input_sha256=$inputSha;report_cell_checks=10420;
  parent=[ordered]@{cells=5210};child=[ordered]@{cells=5210}}
Write-Fixture $behavior
Assert-CheckerVerdict 'check_behavior' $path $runId $inputSha $exportSha|Out-Null
foreach($field in @('schema','passed','run_id','input_sha256','report_cell_checks','parent','child')) {
  $bad=ConvertFrom-Json -InputObject (ConvertTo-Json -InputObject $behavior -Depth 8)
  switch($field) {
    'schema'{$bad.schema='wrong'} 'passed'{$bad.passed='true'}
    'run_id'{$bad.run_id='wrong'} 'input_sha256'{$bad.input_sha256='b'*64}
    'report_cell_checks'{$bad.report_cell_checks='10420'}
    'parent'{$bad.parent.cells=5209} 'child'{$bad.child.cells=5209}
  }
  Write-Fixture $bad;Reject 'check_behavior';$rejections++
}
Write-Fixture $behavior
Reject 'unknown_checker';$rejections++
$resolved=[IO.Path]::GetFullPath($dir);$system=[IO.Path]::GetFullPath($env:TEMP)
if (-not $resolved.StartsWith($system,[StringComparison]::OrdinalIgnoreCase)) { throw 'unsafe temp cleanup target' }
Remove-Item -LiteralPath $resolved -Recurse -Force
[ordered]@{schema='c02-var01-v101-checker-receipt-selfcheck/v1';passed=$true;positives=2;
  rejections=$rejections;native_process_started=$false}|ConvertTo-Json -Compress

$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'checker_receipt.ps1')
if ($PSVersionTable.PSVersion.Major -ne 5) { throw 'PS5 checker-receipt test required' }
$dir=Join-Path $env:TEMP ('i03-var06-checker-test-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $dir | Out-Null
$path=Join-Path $dir 'verdict.json'
$runId='i03-var06-out-dt4-v100-ssh-20261008-01'
$inputSha='3ff558fd5389b1d0e67ec93676a79f9cb00f23823f0514bccf5591c90174f694'
$exportSha='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
function Write-Fixture([object]$data) { $data|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $path -Encoding UTF8 }
function Reject([string]$stage) {
  $failed=$false
  try { Assert-CheckerVerdict $stage $path $runId $inputSha $exportSha|Out-Null } catch { $failed=$true }
  if (-not $failed) { throw "bad $stage JSON was accepted" }
}
$roundtrip=[ordered]@{schema='i03-var06-out-dt4-roundtrip/v1';passed=$true;issues=@();
  row_containing_tables=21;table_objects=32;all_null_placeholder_tables=11;
  input_sha256=$inputSha;export_sha256=$exportSha}
Write-Fixture $roundtrip
Assert-CheckerVerdict 'check_import_export' $path $runId $inputSha $exportSha|Out-Null
$rejections=0
foreach($field in @('schema','passed','issues','row_containing_tables','table_objects','all_null_placeholder_tables','input_sha256','export_sha256')) {
  $bad=[ordered]@{};foreach($key in $roundtrip.Keys){$bad[$key]=$roundtrip[$key]}
  switch($field) {
    'schema'{$bad[$field]='wrong'} 'passed'{$bad[$field]='true'}
    'issues'{$bad[$field]=@('drift')} 'row_containing_tables'{$bad[$field]='21'}
    'table_objects'{$bad[$field]='32'} 'all_null_placeholder_tables'{$bad[$field]='11'}
    'input_sha256'{$bad[$field]='b'*64} 'export_sha256'{$bad[$field]='b'*64}
  }
  Write-Fixture $bad;Reject 'check_import_export';$rejections++
}
[IO.File]::WriteAllText($path,'{invalid',[Text.UTF8Encoding]::new($false))
Reject 'check_import_export';$rejections++
$behavior=[ordered]@{schema='i03-var06-out-dt4-behavior/v1';passed=$true;run_id=$runId;
  input_sha256=$inputSha;report_cell_checks=5210;typed_event_records=99;
  timeline=[ordered]@{terminal_free_crew=1}}
Write-Fixture $behavior
Assert-CheckerVerdict 'check_behavior' $path $runId $inputSha $exportSha|Out-Null
foreach($field in @('schema','passed','run_id','input_sha256','report_cell_checks','typed_event_records','timeline')) {
  $bad=ConvertFrom-Json -InputObject (ConvertTo-Json -InputObject $behavior -Depth 8)
  switch($field) {
    'schema'{$bad.schema='wrong'} 'passed'{$bad.passed='true'}
    'run_id'{$bad.run_id='wrong'} 'input_sha256'{$bad.input_sha256='b'*64}
    'report_cell_checks'{$bad.report_cell_checks='5210'}
    'typed_event_records'{$bad.typed_event_records='99'} 'timeline'{$bad.timeline.terminal_free_crew=0}
  }
  Write-Fixture $bad;Reject 'check_behavior';$rejections++
}
Write-Fixture $behavior
Reject 'unknown_checker';$rejections++
$resolved=[IO.Path]::GetFullPath($dir);$system=[IO.Path]::GetFullPath($env:TEMP)
if (-not $resolved.StartsWith($system,[StringComparison]::OrdinalIgnoreCase)) { throw 'unsafe temp cleanup target' }
Remove-Item -LiteralPath $resolved -Recurse -Force
[ordered]@{schema='i03-var06-out-dt4-checker-receipt-selfcheck/v1';passed=$true;positives=2;
  rejections=$rejections;native_process_started=$false}|ConvertTo-Json -Compress

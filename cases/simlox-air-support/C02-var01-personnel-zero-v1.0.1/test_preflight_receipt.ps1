$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'preflight_receipt.ps1')
$map = [ordered]@{child_contract=('a'*64);runner_script=('b'*64)}
$runId = 'c02-var01-v101-personnel0-ssh-20261007-01'
$manifestSha = 'c'*64
$base = [ordered]@{schema='c02-var01-v101-ssh-preflight/v1';run_id=$runId;run_dirs_absent=$true;
  ssh_session=0;ps_major=5;ssh_ancestors=@('powershell.exe','sshd.exe');mutex_free=$true;wts_active_gui_count=1;
  gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
  accepted_raw_seals=55;accepted_closures=5;accepted_invocations=5;manifest_sha256=$manifestSha;
  source_map_sha256=(Get-SourceMapSha $map);source_hashes=$map;native_process_started=$false}
function Clone-Receipt { ConvertFrom-Json -InputObject (ConvertTo-Json -InputObject $base -Depth 10) }
function Reject([scriptblock]$action,[string]$label) {
  try { & $action; throw "ESCAPED $label" }
  catch { if ($_.Exception.Message -like 'ESCAPED*') { throw }; $script:rejected++ }
}
$rejected = 0
[void](Assert-PreflightReceiptData (Clone-Receipt) $runId $manifestSha $map)
$mutations = @(
  @{field='schema';value='wrong'}, @{field='run_id';value='wrong'},
  @{field='manifest_sha256';value=('d'*64)}, @{field='source_map_sha256';value=('e'*64)},
  @{field='ssh_session';value=1}, @{field='ps_major';value=7},
  @{field='ssh_ancestors';value=@('powershell.exe')}, @{field='mutex_free';value=$false},
  @{field='wts_active_gui_count';value=0}, @{field='run_dirs_absent';value=$false},
  @{field='native_process_started';value=$true}, @{field='accepted_raw_seals';value=54}
)
foreach ($m in $mutations) {
  $receipt = Clone-Receipt
  $receipt.($m.field) = $m.value
  Reject { Assert-PreflightReceiptData $receipt $runId $manifestSha $map } $m.field
}
foreach ($field in @('pid','session_id','start_unix_ms','responding')) {
  $receipt = Clone-Receipt
  $receipt.gui.$field = if ($field -eq 'responding') { $false } else { 0 }
  Reject { Assert-PreflightReceiptData $receipt $runId $manifestSha $map } "gui.$field"
}
foreach ($field in @('ssh_session','ps_major','wts_active_gui_count','accepted_raw_seals')) {
  $receipt = Clone-Receipt
  $receipt.$field = [string]$receipt.$field
  Reject { Assert-PreflightReceiptData $receipt $runId $manifestSha $map } "string typed $field"
}
foreach ($field in @('mutex_free','run_dirs_absent','native_process_started')) {
  $receipt = Clone-Receipt
  $receipt.$field = [string]$receipt.$field
  Reject { Assert-PreflightReceiptData $receipt $runId $manifestSha $map } "string typed $field"
}
foreach ($field in @('pid','session_id','start_unix_ms','responding')) {
  $receipt = Clone-Receipt
  $receipt.gui.$field = [string]$receipt.gui.$field
  Reject { Assert-PreflightReceiptData $receipt $runId $manifestSha $map } "string typed gui.$field"
}
$receipt = Clone-Receipt
$receipt.source_hashes.runner_script = 'f'*64
Reject { Assert-PreflightReceiptData $receipt $runId $manifestSha $map } 'source map content'
$receipt = Clone-Receipt
$receipt.source_hashes | Add-Member -NotePropertyName unexpected -NotePropertyValue ('f'*64)
Reject { Assert-PreflightReceiptData $receipt $runId $manifestSha $map } 'source map extra key'
$temp = Join-Path ([System.IO.Path]::GetTempPath()) ('c02-v101-receipt-' + [guid]::NewGuid().ToString('N'))
try {
  $review = Join-Path $temp 'review'
  [void](New-Item -ItemType Directory -Path $review -Force)
  $relative = 'review\preflight-ssh0-20261007T050000000Z.json'
  $path = Join-Path $temp $relative
  ConvertTo-Json -InputObject $base -Depth 10 | Set-Content -LiteralPath $path -Encoding UTF8
  $sha = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
  $resolved = Assert-PreflightReceiptPath $temp $relative $sha $runId $manifestSha $map
  if ($resolved -ne [System.IO.Path]::GetFullPath($path)) { throw 'owned path did not resolve exactly' }
  Reject { Assert-PreflightReceiptPath $temp 'review\..\preflight-ssh0-20261007T050000000Z.json' $sha $runId $manifestSha $map } 'traversal'
  Reject { Assert-PreflightReceiptPath $temp 'review\..\review\preflight-ssh0-20261007T050000000Z.json' $sha $runId $manifestSha $map } 'traversal returning within review'
  Reject { Assert-PreflightReceiptPath $temp $relative ('0'*64) $runId $manifestSha $map } 'receipt byte seal'
  $outside = Join-Path $temp 'outside'
  $junctionCase = Join-Path $temp 'junction-case'
  [void](New-Item -ItemType Directory -Path $outside)
  [void](New-Item -ItemType Directory -Path $junctionCase)
  Copy-Item -LiteralPath $path -Destination (Join-Path $outside 'preflight-ssh0-20261007T050000000Z.json')
  $junction = Join-Path $junctionCase 'review'
  [void](New-Item -ItemType Junction -Path $junction -Target $outside)
  Reject { Assert-PreflightReceiptPath $junctionCase $relative $sha $runId $manifestSha $map } 'review reparse escape'
} finally {
  $resolvedTemp = [System.IO.Path]::GetFullPath($temp)
  $systemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
  if (-not $resolvedTemp.StartsWith($systemTemp,[System.StringComparison]::OrdinalIgnoreCase)) { throw 'unsafe static temp target' }
  if (Test-Path -LiteralPath $resolvedTemp) {
    $junction = Join-Path (Join-Path $resolvedTemp 'junction-case') 'review'
    if (Test-Path -LiteralPath $junction) { [System.IO.Directory]::Delete($junction) }
    Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
  }
}
[ordered]@{schema='c02-var01-v101-preflight-receipt-self-check/v1';positive=2;rejections=$rejected;
  native_process_started=$false} | ConvertTo-Json -Compress

param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$case=(Resolve-Path $PSScriptRoot).Path
. (Join-Path $case 'captured_process.ps1')
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$child=Join-Path $case 'binary_capture_child.py'
if (Test-Path -LiteralPath $OutputDirectory) { throw 'test output directory already exists' }
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
$session=[int](Get-Process -Id $PID).SessionId
$wantOut=[byte[]](79,85,84,255,0,13,10,65,128,10)
$wantErr=[byte[]](69,82,82,254,0,13,10,66,129,10)
function Equal-Bytes([byte[]]$actual,[byte[]]$expected) {
  if ($actual.Length -ne $expected.Length) { return $false }
  for ($i=0;$i -lt $actual.Length;$i++) { if ($actual[$i] -ne $expected[$i]) { return $false } }
  return $true
}
function Rejected([scriptblock]$probe) {
  try { & $probe | Out-Null; return $false } catch { return $true }
}
$records=@()
foreach ($spec in @(@{name='exit0';code=0;inject=$false},
                   @{name='exit7';code=7;inject=$false},
                   @{name='observed-error';code=0;inject=$true})) {
  $out=Join-Path $OutputDirectory ($spec.name+'.stdout.bin')
  $err=Join-Path $OutputDirectory ($spec.name+'.stderr.bin')
  $args='-X utf8 -B "{0}" --exit {1} --sleep 0.2' -f $child,$spec.code
  $capture=Invoke-CapturedProcess $python $args $case $out $err $session ([bool]$spec.inject)
  if ($capture.child_pid -isnot [int] -or $capture.child_pid -le 0 -or
      $capture.exit_code -isnot [int] -or $capture.exit_code -ne $spec.code -or
      -not (Equal-Bytes ([System.IO.File]::ReadAllBytes($out)) $wantOut) -or
      -not (Equal-Bytes ([System.IO.File]::ReadAllBytes($err)) $wantErr)) {
    throw "original binary capture or OS status differs: $($spec.name)"
  }
  if ($spec.inject) {
    if ($null -ne $capture.child_session_id -or -not $capture.capture_error -or
        -not (Rejected { Assert-SuccessfulCapture $capture $session })) {
      throw 'injected post-start observation failure was not preserved and rejected'
    }
  } else {
    Assert-CapturedProcessRecord $capture $session | Out-Null
    if ($spec.code -eq 0) { Assert-SuccessfulCapture $capture $session | Out-Null }
    elseif (-not (Rejected { Assert-SuccessfulCapture $capture $session })) {
      throw 'integer OS exit7 advanced production gate'
    }
  }
  $records+=,$capture
}
$good=$records[0]
$rejections=0
foreach ($field in @('child_pid','child_session_id','exit_code','stdout_bytes','stderr_bytes')) {
  foreach ($bad in @($null,'0',$false)) {
    $test=[ordered]@{}
    foreach ($key in $good.Keys) { $test[$key]=$good[$key] }
    $test[$field]=$bad
    if (-not (Rejected { Assert-CapturedProcessRecord $test $session })) {
      throw "type/value mutation escaped: $field"
    }
    $rejections++
  }
}
foreach ($field in @('stdout_sha256','stderr_sha256')) {
  $test=[ordered]@{}
  foreach ($key in $good.Keys) { $test[$key]=$good[$key] }
  $test[$field]='0'*64
  if (-not (Rejected { Assert-CapturedProcessRecord $test $session })) {
    throw "wrong stream SHA escaped: $field"
  }
  $rejections++
}
$receipt=[ordered]@{
  schema='i03-var06-binary-capture-test/v1';passed=$true;native_process_started=$false
  session_id=$session;helper_sha256=(Get-FileHash -LiteralPath (Join-Path $case 'captured_process.ps1') -Algorithm SHA256).Hash.ToLowerInvariant()
  test_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
  child_sha256=(Get-FileHash -LiteralPath $child -Algorithm SHA256).Hash.ToLowerInvariant()
  tested_integer_exits=@(0,7);injected_observation_joined=$true
  semantic_rejections=$rejections;records=$records
}
$receiptPath=Join-Path $OutputDirectory 'receipt.json'
if (Test-Path -LiteralPath $receiptPath) { throw 'receipt path unexpectedly exists' }
$receipt | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
Write-Output $receiptPath

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
foreach ($spec in @(@{name='exit0';code=0;inject=$false;drain=$false;async=$false;repeat=1},
                   @{name='exit7';code=7;inject=$false;drain=$false;async=$false;repeat=1},
                   @{name='observed-error';code=0;inject=$true;drain=$false;async=$false;repeat=1},
                   @{name='drain-setup-error';code=0;inject=$false;drain=$true;async=$false;repeat=1},
                   @{name='async-drain-error-large';code=0;inject=$false;drain=$false;async=$true;repeat=131072})) {
  $out=Join-Path $OutputDirectory ($spec.name+'.stdout.bin')
  $err=Join-Path $OutputDirectory ($spec.name+'.stderr.bin')
  $args='-X utf8 -B "{0}" --exit {1} --sleep 0.2 --repeat {2}' -f $child,$spec.code,$spec.repeat
  $capture=Invoke-CapturedProcess $python $args $case $out $err $session ([bool]$spec.inject) ([bool]$spec.drain) ([bool]$spec.async)
  $binaryMatch=$false
  if ($spec.repeat -eq 1) {
    $binaryMatch=(Equal-Bytes ([System.IO.File]::ReadAllBytes($out)) $wantOut) -and
                 (Equal-Bytes ([System.IO.File]::ReadAllBytes($err)) $wantErr)
  } else {
    $binaryMatch=((Get-Item -LiteralPath $out).Length -eq 1310720) -and
                 ((Get-Item -LiteralPath $err).Length -eq 1310720) -and
                 ((Get-CapturedFileSha $out) -eq '59fbefaa7b630fd2a180f3a82053459160fc9399581620cac188902330b65710') -and
                 ((Get-CapturedFileSha $err) -eq 'bcb47a46064f9aab6bae4cd119f018c16667b22a71c60557c72e9d262681a488')
  }
  if ($capture.child_pid -isnot [int] -or $capture.child_pid -le 0 -or
      $capture.exit_code -isnot [int] -or $capture.exit_code -ne $spec.code -or
      -not $binaryMatch) {
    throw "original binary capture or OS status differs: $($spec.name)"
  }
  if ($spec.inject -or $spec.drain -or $spec.async) {
    if (($spec.inject -and $null -ne $capture.child_session_id) -or
        (($spec.drain -or $spec.async) -and $capture.child_session_id -ne $session) -or -not $capture.capture_error -or
        -not (Rejected { Assert-SuccessfulCapture $capture $session })) {
      throw 'injected post-start failure was not joined, preserved and rejected'
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
  session_id=$session;helper_sha256=(Get-CapturedFileSha (Join-Path $case 'captured_process.ps1'))
  test_sha256=(Get-CapturedFileSha $PSCommandPath)
  child_sha256=(Get-CapturedFileSha $child)
  tested_integer_exits=@(0,7);injected_observation_joined=$true;injected_drain_setup_joined=$true
  injected_async_drain_large_joined=$true
  semantic_rejections=$rejections;records=$records
}
$receiptPath=Join-Path $OutputDirectory 'receipt.json'
if (Test-Path -LiteralPath $receiptPath) { throw 'receipt path unexpectedly exists' }
$receipt | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
Write-Output $receiptPath

param([switch]$LocalStatic, [string]$ReceiptPath)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$helper = Join-Path $case 'captured_process.ps1'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$run = Join-Path $case 'runs\c09-var02-v107-shortage-ssh-20261007-01'
. $helper

function Sha([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Reject([scriptblock]$candidate, [string]$label) {
  $rejected = $false
  try { & $candidate | Out-Null } catch { $rejected = $true }
  if (-not $rejected) { throw "capture negative accepted: $label" }
}
function Assert-Gui {
  $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne 1 -or -not $p[0].Responding -or
      ([DateTimeOffset]$p[0].StartTime.ToUniversalTime()).ToUnixTimeMilliseconds() -ne 1790590196826) {
    throw 'protected GUI identity changed'
  }
}

$script:receipt = [ordered]@{
  schema='c09-var02-v107-captured-process-harmless-test/v2'
  receipt_id=[Guid]::NewGuid().ToString('N')
  started_utc=(Get-Date).ToUniversalTime().ToString('o')
  local_static=[bool]$LocalStatic
  helper_sha256_before=(Sha $helper)
  test_sha256_before=(Sha $PSCommandPath)
  native_process_started=$false
  status='started'
}
trap {
  $script:receipt.status='failed'
  $script:receipt.error=$_.Exception.Message
  $script:receipt.completed_utc=(Get-Date).ToUniversalTime().ToString('o')
  $script:receipt.helper_sha256_after=(Sha $helper)
  $script:receipt.test_sha256_after=(Sha $PSCommandPath)
  if ($script:receipt.Contains('temp_directory') -and (Test-Path -LiteralPath $script:receipt.temp_directory)) {
    $script:receipt.partial_raw=@(Get-ChildItem -LiteralPath $script:receipt.temp_directory -File | Sort-Object Name | ForEach-Object {
      [ordered]@{path=$_.FullName;bytes=$_.Length;sha256=(Sha $_.FullName)}
    })
  }
  if ($ReceiptPath -and -not (Test-Path -LiteralPath $ReceiptPath)) {
    $script:receipt | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
  }
  Write-Error $script:receipt.error
  exit 1
}

if ($PSVersionTable.PSVersion.Major -ne 5) { throw 'PowerShell 5 required for process-helper test' }
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'bundled Python absent' }
if (Test-Path -LiteralPath $run) { throw 'reserved v107 native run already exists' }
$session = (Get-Process -Id $PID).SessionId
$ancestors = @()
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorPid = $ancestor.ParentProcessId
}
$mutexFree = $null
$guiVerified = $false
if (-not $LocalStatic) {
  if (-not $env:SSH_CONNECTION -or $session -ne 0 -or $ancestors -notcontains 'sshd.exe') { throw 'actual SSH session0 required' }
  Assert-Gui
  $guiVerified = $true
  $mutex = [System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue')
  try {
    try { $mutexFree = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $mutexFree = $true }
    if (-not $mutexFree) { throw 'native queue mutex busy' }
  } finally {
    if ($mutexFree) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
  }
}

$tmp = Join-Path $env:TEMP ('c09-v107-capture-test-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
$script:receipt.temp_directory=$tmp
$cases = @()
$records = @()
foreach ($expected in @(0,7)) {
  $stdout = Join-Path $tmp ("python-$expected-stdout.txt")
  $stderr = Join-Path $tmp ("python-$expected-stderr.txt")
  $args = '-X utf8 -c "import sys,time;print(''capture-test'');print(''stderr-test'',file=sys.stderr);time.sleep(0.25);sys.exit(' + $expected + ')"'
  $rec = Invoke-CapturedProcess $python $args $case $stdout $stderr $session
  $records += $rec
  if ($rec.exit_code -ne $expected -or $rec.child_session_id -ne $session -or
      (Get-Content -LiteralPath $stdout -Raw -Encoding UTF8) -notmatch 'capture-test' -or
      (Get-Content -LiteralPath $stderr -Raw -Encoding UTF8) -notmatch 'stderr-test') {
    throw "harmless Python OS exit $expected not captured exactly"
  }
  $cases += [ordered]@{expected_exit=$expected;observed_exit=$rec.exit_code;pid=$rec.child_pid;
    session_id=$rec.child_session_id;stdout=[ordered]@{path=$stdout;bytes=(Get-Item -LiteralPath $stdout).Length;sha256=(Sha $stdout)};
    stderr=[ordered]@{path=$stderr;bytes=(Get-Item -LiteralPath $stderr).Length;sha256=(Sha $stderr)}}
}
Assert-SuccessfulCapture $records[0] $session | Out-Null
Reject { Assert-SuccessfulCapture $records[1] $session } 'integer exit 7 cannot advance'; $rejections = 1

foreach ($expected in @(0,7)) {
  $stdout = Join-Path $tmp ("python-fast-$expected-stdout.txt")
  $stderr = Join-Path $tmp ("python-fast-$expected-stderr.txt")
  $args = '-X utf8 -c "import sys;sys.exit(' + $expected + ')"'
  $rec = Invoke-CapturedProcess $python $args $case $stdout $stderr $session
  Assert-CapturedProcessRecord $rec $session | Out-Null
  if ($rec.exit_code -ne $expected) { throw "fast Python $expected OS exit differed" }
  if ($expected -eq 0) { Assert-SuccessfulCapture $rec $session | Out-Null }
  else { Reject { Assert-SuccessfulCapture $rec $session } 'fast integer exit 7 cannot advance'; $rejections++ }
  $cases += [ordered]@{expected_exit=$expected;observed_exit=$rec.exit_code;pid=$rec.child_pid;
    session_id=$rec.child_session_id;fast_exit=$true;
    stdout=[ordered]@{path=$stdout;bytes=(Get-Item -LiteralPath $stdout).Length;sha256=(Sha $stdout)};
    stderr=[ordered]@{path=$stderr;bytes=(Get-Item -LiteralPath $stderr).Length;sha256=(Sha $stderr)}}
}

$failedStdout = Join-Path $tmp 'injected-stdout.txt'
$failedStderr = Join-Path $tmp 'injected-stderr.txt'
$injectedArgs = '-X utf8 -c "import os,time;print(os.getpid());time.sleep(0.25)"'
$injectedRecord = Invoke-CapturedProcess $python $injectedArgs $case $failedStdout $failedStderr $session $true
Reject { Assert-SuccessfulCapture $injectedRecord $session } 'post-Start session observation failure'
$rejections++
$injectedPid = [int](Get-Content -LiteralPath $failedStdout -Raw -Encoding UTF8).Trim()
if ($injectedRecord.child_pid -ne $injectedPid -or $injectedRecord.exit_code -isnot [int] -or
    $injectedRecord.exit_code -ne 0 -or $injectedRecord.child_session_id -ne $null -or
    $injectedRecord.capture_error -notmatch 'injected post-Start') {
  throw 'failed observation lost known PID, OS exit or error context'
}
if (Get-Process -Id $injectedPid -ErrorAction SilentlyContinue) { throw 'injected failure left harmless child alive' }
if (-not (Test-Path -LiteralPath $failedStderr -PathType Leaf)) { throw 'injected failure did not preserve stderr' }
$injectedCapture = [ordered]@{pid=$injectedPid;child_exited=$true;observed_exit=$injectedRecord.exit_code;
  observed_session=$injectedRecord.child_session_id;capture_error=$injectedRecord.capture_error;
  stdout=[ordered]@{path=$failedStdout;bytes=(Get-Item -LiteralPath $failedStdout).Length;sha256=(Sha $failedStdout)};
  stderr=[ordered]@{path=$failedStderr;bytes=(Get-Item -LiteralPath $failedStderr).Length;sha256=(Sha $failedStderr)}}

$valid = [ordered]@{child_pid=[int]123;child_session_id=[int]$session;exit_code=[int]0;
  stdout_path=(Join-Path $tmp 'python-0-stdout.txt');stderr_path=(Join-Path $tmp 'python-0-stderr.txt');capture_error=$null}
Assert-CapturedProcessRecord $valid $session | Out-Null
foreach ($field in @('child_pid','child_session_id','exit_code','stdout_path','stderr_path')) {
  foreach ($replacement in @($null, '0', $true)) {
    $bad = [ordered]@{}; foreach ($key in $valid.Keys) { $bad[$key]=$valid[$key] }; $bad[$field]=$replacement
    Reject { Assert-CapturedProcessRecord $bad $session } "$field replacement"
    $rejections++
  }
  $bad = [ordered]@{}; foreach ($key in $valid.Keys) { if ($key -ne $field) { $bad[$key]=$valid[$key] } }
  Reject { Assert-CapturedProcessRecord $bad $session } "$field missing"
  $rejections++
}
Reject { Assert-CapturedProcessRecord $null $session } 'null record'; $rejections++
Reject { Assert-CapturedProcessRecord 'malformed' $session } 'malformed record'; $rejections++
$bad = [ordered]@{}; foreach ($key in $valid.Keys) { $bad[$key]=$valid[$key] }; $bad.child_session_id=[int]($session+1)
Reject { Assert-CapturedProcessRecord $bad $session } 'wrong session'; $rejections++

if (-not $LocalStatic) { Assert-Gui }
$result = $script:receipt
$result.completed_utc=(Get-Date).ToUniversalTime().ToString('o')
$result.powershell_major=$PSVersionTable.PSVersion.Major
$result.ssh_session=$session
$result.ssh_ancestors=$ancestors
$result.gui_verified=$guiVerified
$result.mutex_free=$mutexFree
$result.run_absent=(-not (Test-Path -LiteralPath $run))
$result.helper_sha256_after=(Sha $helper)
$result.test_sha256_after=(Sha $PSCommandPath)
if ($result.helper_sha256_after -ne $result.helper_sha256_before -or $result.test_sha256_after -ne $result.test_sha256_before) {
  throw 'production helper or test changed while harmless children ran'
}
$result.contract_sha256=(Sha (Join-Path $case 'contract.json'))
$result.harmless_python=$cases
$result.injected_post_start_failure=$injectedCapture
$result.negative_rejections=$rejections
$result.status='passed'
if ($ReceiptPath) {
  if (Test-Path -LiteralPath $ReceiptPath) { throw 'test receipt path already exists' }
  $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
}
$result | ConvertTo-Json -Depth 8

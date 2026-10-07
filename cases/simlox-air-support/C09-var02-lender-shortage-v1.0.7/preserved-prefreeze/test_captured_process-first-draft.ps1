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
$cases = @()
foreach ($expected in @(0,7)) {
  $stdout = Join-Path $tmp ("python-$expected-stdout.txt")
  $stderr = Join-Path $tmp ("python-$expected-stderr.txt")
  $args = '-X utf8 -c "import sys,time;print(''capture-test'');print(''stderr-test'',file=sys.stderr);time.sleep(0.25);sys.exit(' + $expected + ')"'
  $rec = Invoke-CapturedProcess $python $args $case $stdout $stderr $session
  if ($rec.exit_code -ne $expected -or $rec.child_session_id -ne $session -or
      (Get-Content -LiteralPath $stdout -Raw -Encoding UTF8) -notmatch 'capture-test' -or
      (Get-Content -LiteralPath $stderr -Raw -Encoding UTF8) -notmatch 'stderr-test') {
    throw "harmless Python OS exit $expected not captured exactly"
  }
  $cases += [ordered]@{expected_exit=$expected;observed_exit=$rec.exit_code;pid=$rec.child_pid;
    session_id=$rec.child_session_id;stdout_sha256=(Sha $stdout);stderr_sha256=(Sha $stderr)}
}

$valid = [ordered]@{child_pid=[int]123;child_session_id=[int]$session;exit_code=[int]0;
  stdout_path=(Join-Path $tmp 'python-0-stdout.txt');stderr_path=(Join-Path $tmp 'python-0-stderr.txt')}
Assert-CapturedProcessRecord $valid $session | Out-Null
$rejections = 0
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
$result = [ordered]@{schema='c09-var02-v107-captured-process-harmless-test/v1';
  completed_utc=(Get-Date).ToUniversalTime().ToString('o');local_static=[bool]$LocalStatic;
  powershell_major=$PSVersionTable.PSVersion.Major;ssh_session=$session;ssh_ancestors=$ancestors;
  gui_verified=$guiVerified;mutex_free=$mutexFree;native_process_started=$false;run_absent=(-not (Test-Path -LiteralPath $run));
  helper_sha256=(Sha $helper);test_sha256=(Sha $PSCommandPath);contract_sha256=(Sha (Join-Path $case 'contract.json'));
  harmless_python=$cases;negative_rejections=$rejections;status='passed'}
if ($ReceiptPath) {
  if (Test-Path -LiteralPath $ReceiptPath) { throw 'test receipt path already exists' }
  $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
}
$result | ConvertTo-Json -Depth 8

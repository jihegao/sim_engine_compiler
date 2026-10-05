$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$runner = Join-Path $case 'run_native_ssh.ps1'
$run = Join-Path (Join-Path $case 'runs') 'd03-var02-mission245-v012-ssh-20261006-01'
$pythonPath = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0) { throw 'SSH session zero required' }
if (Test-Path -LiteralPath $run) { throw 'reserved native run path already exists' }
$ancestorNames = @()
$parentPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $parentPid -gt 0; $depth++) {
  $p = Get-CimInstance Win32_Process -Filter "ProcessId=$parentPid"
  if (-not $p) { break }
  $ancestorNames += $p.Name
  $parentPid = $p.ParentProcessId
}
if ($ancestorNames -notcontains 'sshd.exe') { throw 'sshd ancestor absent' }
$gui = @(Get-Process Simlox -ErrorAction SilentlyContinue)
if ($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -ne 1 -or -not $gui[0].Responding -or ([DateTimeOffset]$gui[0].StartTime.ToUniversalTime()).ToUnixTimeMilliseconds() -ne 1790590196826) { throw 'GUI identity or responding state differs' }
$sessions = @(qwinsta 2>&1)
if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match '^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+1\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)' }).Count -ne 1) { throw 'GUI session 1 not active' }
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile($runner, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -ne 0) { throw 'runner does not parse in this PowerShell' }
& $pythonPath (Join-Path $case 'build.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'builder invocation failed under SSH PowerShell' }
& $pythonPath (Join-Path $case 'check_parent_diff.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'diff checker invocation failed under SSH PowerShell' }
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'native mutex held by another owner' }
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}
[ordered]@{
  schema='simlox-d03-var02-v012-readonly-preflight/v1'
  session_id=0
  ssh_ancestor=$true
  gui_pid=$gui[0].Id
  gui_session=$gui[0].SessionId
  gui_start_utc=$gui[0].StartTime.ToUniversalTime().ToString('o')
  gui_responding=$gui[0].Responding
  gui_session_active=$true
  simlox_process_count=$gui.Count
  native_mutex_available=$true
  reserved_run_absent=$true
  runner_ps5_parser_errors=0
  builder_and_diff_invocation='passed'
} | ConvertTo-Json

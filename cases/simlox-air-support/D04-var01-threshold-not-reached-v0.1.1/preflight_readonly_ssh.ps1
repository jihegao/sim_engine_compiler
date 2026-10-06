$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$runner = Join-Path $case 'run_native_ssh.ps1'
$run = Join-Path (Join-Path $case 'runs') 'd04-var01-op4-v011-ssh-20261006-01'
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
foreach ($item in @(
  @((Join-Path $case 'contract.json'),'a49bd85018977531f8219f2f5fc5e1ebdfa8b5054eb2dc28d54f903ee950b8bd'),
  @((Join-Path $case 'native-input.json'),'cb8d6045df3b395583e3df2290b61376afa4fa9e8bc82a1c6f53fcfb44e2bddd'),
  @((Join-Path $case 'review\independent-contract-go-2026-10-06.md'),'f74feebd7b8743657f43abd59441056314e65270134d7f9323da2e5842cf0c57'),
  @((Join-Path (Split-Path $case -Parent) 'D04-flight-hour-pm-v1.0.0\native-input.json'),'d0b0ee5b74f3afe5f05b418771774adcf8ef987b0f553f1bfd535874955c790a'),
  @((Join-Path (Split-Path $case -Parent) 'D03-calendar-pm-v1.0.0\native-input.json'),'5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32'),
  @('C:\Program Files\Systecon\SIMLOX\Simlox.exe','fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
)) {
  if ((Get-FileHash -LiteralPath $item[0] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item[1]) { throw "preflight source fingerprint differs: $($item[0])" }
}
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
  schema='simlox-d04-var01-v011-readonly-preflight/v1'
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

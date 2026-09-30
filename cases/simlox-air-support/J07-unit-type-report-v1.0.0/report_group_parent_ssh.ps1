param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
  [Parameter(Mandatory=$true)][ValidateSet('all','group','unit-a','unit-b')][string]$Selector
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$parentCase = Join-Path (Split-Path $case -Parent) 'A17-multi-unit-group-v1.0.0'
$sourceRun = Join-Path $parentCase 'runs\a17-v100-ssh-20260929-01'
$sxo = Join-Path $sourceRun 'model.sxo'
$sourceClosure = Join-Path $sourceRun 'closure.json'
$settings = Join-Path $case ("runs\report-settings\$Selector.sxs")
$default = 'C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$expected = [ordered]@{
  sxo = 'f4c2fcd42c5620ec6e7adf163962bb6001a4a9acf49eee8d7adfeba50113349b'
  default = '1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d'
  exe = 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
}
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
$ancestors = @()
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'cannot verify sshd ancestor' }
if ((Get-FileHash $sxo -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected.sxo) { throw 'source sxo changed' }
if ((Get-FileHash $default -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected.default) { throw 'default settings changed' }
if ((Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected.exe) { throw 'exe changed' }
$sourceSeal = Get-Content $sourceClosure -Raw | ConvertFrom-Json
if ($sourceSeal.error -or $sourceSeal.raw.'model.sxo'.sha256 -ne $expected.sxo) { throw 'source closure invalid' }
$settingsSha = (Get-FileHash $settings -Algorithm SHA256).Hash.ToLowerInvariant()
$runnerSha = (Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
$run = Join-Path (Join-Path $case 'runs\report-settings') $RunId
if (Test-Path $run) { throw 'immutable run already exists' }
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'native queue busy' }
  $gui = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -le 0) { throw 'GUI identity differs' }
  $guiStart = $gui[0].StartTime.ToUniversalTime().ToString('o')
  $guiSession = $gui[0].SessionId
  $sessions = @(qwinsta 2>&1)
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session not active' }
  New-Item -ItemType Directory -Path $run | Out-Null
  $report = Join-Path $run 'report-raw.json'
  $log = Join-Path $run 'report-export.log'
  $args = ('"{0}" -silent -report -rpts "{1}" -rjexport "{2}" -log "{3}" -close' -f $sxo,$settings,$report,$log)
  $invocation = [ordered]@{run_id=$RunId;selector=$Selector;scope='report_only_candidate';source_sxo_sha256=$expected.sxo;source_closure_sha256=(Get-FileHash $sourceClosure -Algorithm SHA256).Hash.ToLowerInvariant();settings_sha256=$settingsSha;installed_default_sha256=$expected.default;exe_sha256=$expected.exe;runner_sha256=$runnerSha;gui_pid=13340;gui_session=$guiSession;gui_start_utc=$guiStart;ssh_ancestors=$ancestors;command=$args}
  $invocation | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $run 'invocation.json') -Encoding UTF8
  $p = Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
  $guiAfter = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($p.ExitCode -ne 0 -or $guiAfter.Count -ne 1 -or $guiAfter[0].Id -ne 13340 -or $guiAfter[0].SessionId -ne $guiSession -or $guiAfter[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'report or GUI guard failed' }
  if ((Get-FileHash $sxo -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected.sxo -or (Get-FileHash $settings -Algorithm SHA256).Hash.ToLowerInvariant() -ne $settingsSha -or (Get-FileHash $default -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected.default -or (Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected.exe -or (Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $runnerSha) { throw 'source changed after report' }
  $raw = @{}
  foreach ($file in Get-ChildItem $run -File) { if ($file.Name -ne 'invocation.json') { $raw[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-FileHash $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} } }
  [ordered]@{run_id=$RunId;exit_code=$p.ExitCode;invocation_sha256=(Get-FileHash (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();source_sxo_sha256=$expected.sxo;settings_sha256=$settingsSha;runner_sha256=$runnerSha;raw=$raw;scope='report_only_candidate'} | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $run 'closure.json') -Encoding UTF8
  Write-Output ([ordered]@{run_id=$RunId;exit_code=$p.ExitCode;report=$report} | ConvertTo-Json)
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

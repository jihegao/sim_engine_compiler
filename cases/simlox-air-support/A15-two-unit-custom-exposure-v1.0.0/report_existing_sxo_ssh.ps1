param(
  [Parameter(Mandatory=$true)][ValidateSet('a-hour-b-mission','a-mission-b-hour')][string]$Variant,
  [Parameter(Mandatory=$true)][ValidateSet('all','unit-a','unit-b')][string]$Selector,
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$sourceId = if ($Variant -eq 'a-hour-b-mission') { 'a15-two-unit-swap-a-v100-20261001-01' } else { 'a15-two-unit-swap-b-v100-20261001-01' }
$expectedSxo = if ($Variant -eq 'a-hour-b-mission') { '7347162aaff3c017b66da2b8b4d7d653db7d7ab1b7c1e0d9814bb10b145c372e' } else { '7bed452f7eb37ba236d616263fc9529241be83fd65f12d04147bc574e9ae1831' }
$expectedClosure = if ($Variant -eq 'a-hour-b-mission') { '38fce23f882537c809bef906dd134b76e16c6c86d4f35c8f2d24eb3cd6ddfd27' } else { 'dca1b507376db23c7300347f0576838ce7317a9049c20844d96067b42df1279b' }
$sourceRun = Join-Path (Join-Path $case 'runs') $sourceId
$sxo = Join-Path $sourceRun 'model.sxo'
$sourceClosure = Join-Path $sourceRun 'closure.json'
$settings = Join-Path $case ("runs\report-settings\$Selector.sxs")
$default = 'C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs'
$builder = Join-Path $case 'make_report_settings.py'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run = Join-Path (Join-Path $case 'runs') $RunId
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
if (Test-Path -LiteralPath $run) { throw 'immutable report run already exists' }
$expected = [ordered]@{
  sxo = $expectedSxo
  closure = $expectedClosure
  settings = switch ($Selector) { 'all' { 'c2f9862c89f2aae0200d8f7a4f16a2e21b7c6ff896b42548c41b98e673f3f9b7' } 'unit-a' { 'aa88c6dfd319640a577fe345933a8bf143bd215fe6514ed915593d5504b12d39' } 'unit-b' { '05074aed026f1c32c8a76992a4fc03dbf222776128a6910dc9b4664bff88ffd4' } }
  default = '1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d'
  exe = 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
}
foreach ($item in @(@($sxo,$expected.sxo),@($sourceClosure,$expected.closure),@($settings,$expected.settings),@($default,$expected.default),@($exe,$expected.exe))) {
  if (-not (Test-Path -LiteralPath $item[0]) -or (Get-FileHash -LiteralPath $item[0] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item[1]) { throw "fingerprint differs: $($item[0])" }
}
$sourceSeal = Get-Content -LiteralPath $sourceClosure -Raw | ConvertFrom-Json
if ($sourceSeal.error -or $sourceSeal.raw.'model.sxo'.sha256 -ne $expected.sxo) { throw 'source closure invalid' }
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide Issue 18 native queue busy' }
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
  $sourceHashes = [ordered]@{sxo=$expected.sxo;source_closure=$expected.closure;settings=$expected.settings;default=$expected.default;exe=$expected.exe;builder=(Get-FileHash -LiteralPath $builder -Algorithm SHA256).Hash.ToLowerInvariant();runner=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()}
  [ordered]@{schema='simlox-a15-two-unit-operation-report-invocation/v1';variant=$Variant;selector=$Selector;run_id=$RunId;source_run_id=$sourceId;source_hashes=$sourceHashes;session_id=(Get-Process -Id $PID).SessionId;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';command=$args;scope='report_only_candidate'} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $errorText = $null
  $exitCode = $null
  try {
    $p = Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
    $exitCode = $p.ExitCode
    $guiAfter = @(Get-Process Simlox -ErrorAction SilentlyContinue)
    if ($exitCode -ne 0 -or $guiAfter.Count -ne 1 -or $guiAfter[0].Id -ne 13340 -or $guiAfter[0].SessionId -ne $guiSession -or $guiAfter[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'report or GUI guard failed' }
    if (-not (Test-Path -LiteralPath $report) -or (Get-Item -LiteralPath $report).Length -le 4) { throw 'report absent or empty' }
    if ((Get-Content -LiteralPath $log -Raw) -match 'could not be loaded|Reverting to default settings|Failed to open file') { throw 'settings rejected; SIMLOX fell back to default' }
  } catch { $errorText = $_.Exception.Message }
  foreach ($item in @(@($sxo,$expected.sxo),@($sourceClosure,$expected.closure),@($settings,$expected.settings),@($default,$expected.default),@($exe,$expected.exe),@($builder,$sourceHashes.builder),@($PSCommandPath,$sourceHashes.runner))) {
    if ((Get-FileHash -LiteralPath $item[0] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item[1]) { $errorText = "source fingerprint changed: $($item[0])" }
  }
  $raw = @{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File) { if ($file.Name -ne 'invocation.json') { $raw[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} } }
  [ordered]@{schema='simlox-a15-two-unit-operation-report-closure/v1';run_id=$RunId;variant=$Variant;selector=$Selector;exit_code=$exitCode;invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();source_hashes=$sourceHashes;raw=$raw;error=$errorText;scope='report_only_candidate'} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{run_id=$RunId;exit_code=$exitCode;report=$report} | ConvertTo-Json)
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

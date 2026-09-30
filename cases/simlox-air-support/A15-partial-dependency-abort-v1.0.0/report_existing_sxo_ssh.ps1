param(
  [Parameter(Mandatory=$true)][ValidateSet('control-hour','control-mission','dependent-hour','dependent-mission')][string]$Variant,
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$sourceId = "a15-partial-$Variant-v100-20261001-01"
$expectedSxo = @{ 'control-hour'='af783d787b590b186dc6bad9dec659912f5e5d2d9085a4e537c0c2df8f737edc'; 'control-mission'='5dd963e213338949232c6ffeedc700418d4b7601cbb1d40c4221dc40e39b104b'; 'dependent-hour'='738810513abd31020f990bdc1b4d933acf295f9e08af971665c2ba2896ee58c4'; 'dependent-mission'='5c34c31a0eeedbff876bea7c6eef0def9bb9baed99090801d88a9caf826c24c0' }[$Variant]
$expectedClosure = @{ 'control-hour'='a61e3234fbd103c826645173bbdd9ba3a8ed8bca29b2076356a2f61bfa29eb0a'; 'control-mission'='b81088c970cf46302062a90631df01d2c44d6b8611819926b228894c4621cf6f'; 'dependent-hour'='93256af2002dcfc7c44a62bcb47649f9cc57c1202407bca29c7077a1aee778c5'; 'dependent-mission'='0c2d534be2efb9826cb4ce4fdbcca2eb9efd19d1c4ba52531d4c429dcff6d65f' }[$Variant]
$sourceRun = Join-Path (Join-Path $case 'runs') $sourceId
$sxo = Join-Path $sourceRun 'model.sxo'
$sourceClosure = Join-Path $sourceRun 'closure.json'
$settings = Join-Path $case 'runs\report-settings\all.sxs'
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
  settings = 'c2f9862c89f2aae0200d8f7a4f16a2e21b7c6ff896b42548c41b98e673f3f9b7'
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
  [ordered]@{schema='simlox-a15-partial-abort-operation-report-invocation/v1';variant=$Variant;run_id=$RunId;source_run_id=$sourceId;source_hashes=$sourceHashes;session_id=(Get-Process -Id $PID).SessionId;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';command=$args;scope='report_only_candidate'} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
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
  [ordered]@{schema='simlox-a15-partial-abort-operation-report-closure/v1';run_id=$RunId;variant=$Variant;exit_code=$exitCode;invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();source_hashes=$sourceHashes;raw=$raw;error=$errorText;scope='report_only_candidate'} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{run_id=$RunId;exit_code=$exitCode;report=$report} | ConvertTo-Json)
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

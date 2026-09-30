param(
  [Parameter(Mandatory=$true)][ValidateSet('direct-control','nested-repeat')][string]$Variant,
  [Parameter(Mandatory=$true)][ValidateSet('default','replications')][string]$SettingsMode,
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$exeSha = 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
$defaultSettings = 'C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs'
$defaultSha = '1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d'
$patchedSettings = Join-Path $case 'runs\report-settings\replications-enabled.sxs'
$patchedSha = '6417a4f4ece02e758b4cae90afb674ec93d3c0b3aa730bdb6334df036d746882'
$sourceId = switch ($Variant) {
  'direct-control' { 'j05-nested-direct-v100-20261001-01' }
  'nested-repeat' { 'j05-nested-repeat-v100-20261001-01' }
}
$expectedSxoSha = switch ($Variant) {
  'direct-control' { 'f9a4210a602838db928322af35ee1c9fd235e2653ca7daad648e99718e30df70' }
  'nested-repeat' { '7b345ed8d146d48747092ce3402837363ada05044cb321360b70d800ccc0924e' }
}
$sourceRun = Join-Path (Join-Path $case 'runs') $sourceId
$sxo = Join-Path $sourceRun 'model.sxo'
$sourceClosure = Join-Path $sourceRun 'closure.json'
$settings = if ($SettingsMode -eq 'default') { $defaultSettings } else { $patchedSettings }
$settingsSha = if ($SettingsMode -eq 'default') { $defaultSha } else { $patchedSha }
$run = Join-Path (Join-Path $case 'runs\report-settings') $RunId
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if (Test-Path -LiteralPath $run) { throw 'immutable report probe already exists' }
$ancestors = @()
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'cannot verify sshd ancestor' }
foreach ($item in @(@($exe,$exeSha),@($defaultSettings,$defaultSha),@($settings,$settingsSha),@($sxo,$expectedSxoSha))) {
  if (-not (Test-Path -LiteralPath $item[0]) -or (Get-FileHash -LiteralPath $item[0] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item[1]) { throw "fingerprint differs: $($item[0])" }
}
$sourceSeal = Get-Content -LiteralPath $sourceClosure -Raw | ConvertFrom-Json
if ($sourceSeal.error -or $sourceSeal.raw.'model.sxo'.sha256 -ne $expectedSxoSha) { throw 'source SXO closure not successful/sealed' }
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned native working directory absent' }
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide Issue 18 native queue busy' }
  $existing = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -le 0) { throw 'expected existing GUI PID 13340 only' }
  $guiStart = $existing[0].StartTime.ToUniversalTime().ToString('o')
  $guiSession = $existing[0].SessionId
  $sessions = @(qwinsta 2>&1)
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session not active' }
  function Assert-Gui {
    $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
    if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'GUI process changed' }
  }
  New-Item -ItemType Directory -Path $run -Force | Out-Null
  $report = Join-Path $run 'report-raw.json'
  $log = Join-Path $run 'report-export.log'
  $args = ('"{0}" -silent -report -rpts "{1}" -rjexport "{2}" -log "{3}" -close' -f $sxo,$settings,$report,$log)
  $sourceHashes = [ordered]@{
    sxo=$expectedSxoSha; source_closure=(Get-FileHash -LiteralPath $sourceClosure -Algorithm SHA256).Hash.ToLowerInvariant()
    settings=$settingsSha; installed_default_settings=$defaultSha; simlox_exe=$exeSha
    runner_script=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
  }
  $invocation = [ordered]@{
    schema='simlox-j05-nested-report-settings-probe/v1'; variant=$Variant; settings_mode=$SettingsMode; run_id=$RunId
    source_run_id=$sourceId; created_utc=(Get-Date).ToUniversalTime().ToString('o')
    host_name=$env:COMPUTERNAME; session_id=(Get-Process -Id $PID).SessionId
    ssh_connection_present=[bool]$env:SSH_CONNECTION; ssh_ancestor_names=$ancestors
    gui=[ordered]@{ pid=13340; session_id=$guiSession; start_utc=$guiStart }
    queue_mutex='Global\SimloxIssue18NativeQueue'; command=$args; source_hashes_before=$sourceHashes
    publication_state='not_published'; scope='report_only_diagnostic'
  }
  $invocation | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $errorText = $null
  $exit = $null
  try {
    Assert-Gui
    $process = Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
    $exit = $process.ExitCode
    Assert-Gui
    if ($exit -ne 0) { throw "report export exit=$exit" }
    foreach ($path in @($report,$log)) {
      if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -le 4) { throw "missing/empty report output $path" }
    }
  } catch { $errorText = $_.Exception.Message }
  $after = [ordered]@{
    sxo=(Get-FileHash -LiteralPath $sxo -Algorithm SHA256).Hash.ToLowerInvariant()
    source_closure=(Get-FileHash -LiteralPath $sourceClosure -Algorithm SHA256).Hash.ToLowerInvariant()
    settings=(Get-FileHash -LiteralPath $settings -Algorithm SHA256).Hash.ToLowerInvariant()
    installed_default_settings=(Get-FileHash -LiteralPath $defaultSettings -Algorithm SHA256).Hash.ToLowerInvariant()
    simlox_exe=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
    runner_script=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
  }
  foreach ($key in $sourceHashes.Keys) { if ($sourceHashes[$key] -ne $after[$key]) { $errorText = "source fingerprint changed: $key" } }
  $raw = @{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File) {
    if ($file.Name -eq 'invocation.json') { continue }
    $raw[$file.Name] = [ordered]@{ bytes=$file.Length; sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
  }
  [ordered]@{ schema='simlox-j05-nested-report-settings-probe-closure/v1'; run_id=$RunId
    invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    exit_code=$exit; error=$errorText; source_hashes_before=$sourceHashes; source_hashes_after=$after
    raw=$raw; scope='report_only_diagnostic'; publication_state='not_published' } |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{ run_id=$RunId; report=$report; exit_code=$exit } | ConvertTo-Json)
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}


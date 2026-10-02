param(
  [Parameter(Mandatory=$true)][ValidateSet('base-01','base-02','depot')][string]$Station,
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId
)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$sourceRunId = 'i02-var08-lateral-out-v100-ssh-20261002-01'
$sourceRun = Join-Path (Join-Path $case 'runs') $sourceRunId
$sxo = Join-Path $sourceRun 'model.sxo'
$sourceClosure = Join-Path $sourceRun 'closure.json'
$settings = Join-Path (Join-Path $case 'runs') "report-settings\$Station-item.sxs"
$run = Join-Path (Join-Path $case 'runs') $RunId
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$sxoSha = '6503f2e9c8582fa27e8f31921488e31869d4dcef4a08890a9d069ce185813441'
$sourceClosureSha = 'e26e9b02301986ee09f23aa3946d8b50a75de2273f77c775b1ec357baab85453'
$settingsSha = switch ($Station) {
  'base-01' { '10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b' }
  'base-02' { '83dfecf3d1d88e56d776ecd84268d1a5728cee256b0dd0e5912bf3a5251589c4' }
  'depot' { '2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9' }
}
$exeSha = 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
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
if ($ancestors -notcontains 'sshd.exe') { throw 'sshd ancestor required' }
$closed = Get-Content -LiteralPath $sourceClosure -Raw | ConvertFrom-Json
if ($closed.error -or $closed.run_id -ne $sourceRunId -or
    (Get-FileHash -LiteralPath $sourceClosure -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sourceClosureSha -or
    $closed.raw.'model.sxo'.sha256 -ne $sxoSha -or
    (Get-FileHash -LiteralPath $sxo -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sxoSha) {
  throw 'sealed source SXO closure differs'
}
foreach ($item in @(@($settings,$settingsSha),@($exe,$exeSha))) {
  if (-not (Test-Path -LiteralPath $item[0]) -or
      (Get-FileHash -LiteralPath $item[0] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item[1]) {
    throw "fingerprint differs: $($item[0])"
  }
}
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'native working directory absent' }
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
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object {
        $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)')
      }).Count -ne 1) { throw 'GUI session not active' }
  function Assert-Gui {
    $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
    if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $guiSession -or
        $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'GUI process changed' }
  }
  New-Item -ItemType Directory -Path $run -Force | Out-Null
  $report = Join-Path $run 'item-report-raw.json'
  $log = Join-Path $run 'report-export.log'
  $argsText = ('"{0}" -silent -report -rpts "{1}" -rjexport "{2}" -log "{3}" -close' -f $sxo,$settings,$report,$log)
  $before = [ordered]@{ sxo=$sxoSha; settings=$settingsSha; exe=$exeSha;
    runner=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant() }
  $invocation = [ordered]@{ schema='simlox-i02-var08-item-report-probe/ssh-cli-v1'; run_id=$RunId;
    station=$Station;
    source_run_id=$closed.run_id; source_closure_sha256=$sourceClosureSha;
    source_hashes_before=$before; execution_mode='ssh_cli_v1'; session_id=(Get-Process -Id $PID).SessionId;
    ssh_ancestor_names=$ancestors; queue_mutex='Global\SimloxIssue18NativeQueue';
    gui=[ordered]@{ pid=13340; session_id=$guiSession; start_utc=$guiStart }; arguments=$argsText;
    scope='item_report_diagnostic'; publication_state='not_published' }
  $invocation | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $errorText = $null
  $exitCode = $null
  try {
    Assert-Gui
    $process = Start-Process -FilePath $exe -ArgumentList $argsText -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
    $exitCode = $process.ExitCode
    Assert-Gui
    if ($exitCode -ne 0 -or -not (Test-Path -LiteralPath $report) -or (Get-Item -LiteralPath $report).Length -le 4) {
      throw 'item report export failed or empty'
    }
  } catch {
    $errorText = $_.Exception.Message
  }
  $after = [ordered]@{ sxo=(Get-FileHash -LiteralPath $sxo -Algorithm SHA256).Hash.ToLowerInvariant();
    settings=(Get-FileHash -LiteralPath $settings -Algorithm SHA256).Hash.ToLowerInvariant();
    exe=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant();
    runner=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant() }
  foreach ($key in $before.Keys) { if ($before[$key] -ne $after[$key]) { $errorText = "fingerprint changed: $key" } }
  $raw = @{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File) {
    if ($file.Name -eq 'invocation.json') { continue }
    $raw[$file.Name] = [ordered]@{ bytes=$file.Length; sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
  }
  [ordered]@{ schema='simlox-i02-var08-item-report-probe-closure/v1'; run_id=$RunId;
    invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();
    source_hashes_before=$before; source_hashes_after=$after; raw=$raw; exit_code=$exitCode;
    error=$errorText; scope='item_report_diagnostic'; publication_state='not_published' } |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { Write-Error $errorText; exit 1 }
  Write-Output ([ordered]@{ run_id=$RunId; report=$report; status='exported' } | ConvertTo-Json)
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}



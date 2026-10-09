param([switch]$PreflightOnly)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$manifestPath = Join-Path $case 'prelaunch-manifest.json'
$approvalPath = Join-Path $case 'review\independent-prelaunch-go.json'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo'
$runId = 'i05-var05-item-replacement-v107-ssh-20261009-01'
$run = 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\tmp\i05-var05-item-replacement-v107-20261009-01'
$mutexName = 'Global\SimloxIssue18NativeQueue'

function Get-Sha([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Assert-Gui {
  $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne 1 -or -not $p[0].Responding -or
      ([DateTimeOffset]$p[0].StartTime.ToUniversalTime()).ToUnixTimeMilliseconds() -ne 1790590196826) {
    throw 'protected GUI PID/session/start/responding changed'
  }
}
function Assert-Wts {
  if (-not ('Issue18WtsNative' -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class Issue18WtsNative {
  [DllImport("wtsapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  private static extern bool WTSQuerySessionInformation(IntPtr server, int sessionId, int infoClass, out IntPtr buffer, out int bytesReturned);
  [DllImport("wtsapi32.dll")]
  private static extern void WTSFreeMemory(IntPtr memory);
  public static int GetConnectState(int sessionId) {
    IntPtr buffer = IntPtr.Zero;
    int bytesReturned = 0;
    if (!WTSQuerySessionInformation(IntPtr.Zero, sessionId, 8, out buffer, out bytesReturned)) throw new Win32Exception(Marshal.GetLastWin32Error());
    try { if (bytesReturned < 4) throw new InvalidOperationException("WTS connect-state response is too short"); return Marshal.ReadInt32(buffer); }
    finally { WTSFreeMemory(buffer); }
  }
}
"@
  }
  if ([Issue18WtsNative]::GetConnectState(1) -ne 0) { throw 'protected GUI WTS session 1 not active' }
}
function Assert-RunAbsent {
  if (-not [System.IO.Path]::IsPathRooted($run) -or [System.IO.Path]::GetFullPath($run) -cne $run) { throw 'run path not canonical' }
  $cursor = [System.IO.Path]::GetPathRoot($run)
  foreach ($part in $run.Substring($cursor.Length).Split([System.IO.Path]::DirectorySeparatorChar)) {
    if ($part -eq '') { continue }
    $cursor = Join-Path $cursor $part
    $item = Get-Item -LiteralPath $cursor -Force -ErrorAction SilentlyContinue
    if ($item -and (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) { throw 'run path traverses reparse point' }
  }
  if (Test-Path -LiteralPath $run) { throw 'reserved run path already exists' }
  $file = (Join-Path $run 'model.sxi').Replace('\','/')
  if ($file -cne [System.Text.Encoding]::ASCII.GetString([System.Text.Encoding]::ASCII.GetBytes($file)) -or
      [System.Text.Encoding]::ASCII.GetByteCount('File: ' + $file) -gt 199) { throw 'native File line is non-ASCII or exceeds 199 bytes' }
}
function Assert-Sources($manifest) {
  foreach ($entry in $manifest.source_files) {
    if (-not (Test-Path -LiteralPath $entry.path -PathType Leaf)) { throw "source missing: $($entry.key)" }
    $item = Get-Item -LiteralPath $entry.path
    if ($item.Length -ne $entry.bytes -or (Get-Sha $entry.path) -cne $entry.sha256 -or [int]$item.Attributes -ne [int]$entry.attributes) {
      throw "source pin mismatch: $($entry.key)"
    }
  }
  $catalog = $manifest.live_catalog_prelaunch_pin
  if (-not $catalog -or -not (Test-Path -LiteralPath $catalog.path -PathType Leaf) -or
      (Get-Item -LiteralPath $catalog.path).Length -ne $catalog.bytes -or (Get-Sha $catalog.path) -cne $catalog.sha256) {
    throw 'live catalog pin mismatch'
  }
  $publicationIndex = $manifest.live_publication_index_prelaunch_pin
  if (-not $publicationIndex -or -not (Test-Path -LiteralPath $publicationIndex.path -PathType Leaf) -or
      (Get-Item -LiteralPath $publicationIndex.path).Length -ne $publicationIndex.bytes -or
      (Get-Sha $publicationIndex.path) -cne $publicationIndex.sha256) {
    throw 'live publication index pin mismatch'
  }
}
function Assert-Environment($manifest, [switch]$BeforeDispatch) {
  if ($PSVersionTable.PSVersion.Major -ne 5 -or -not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) {
    throw 'actual SSH PowerShell 5 session 0 required'
  }
  $script:ancestors = @(); $script:ancestorPids = @(); $parent = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
  for ($i=0; $i -lt 8 -and $parent -gt 0; $i++) { $p=Get-CimInstance Win32_Process -Filter "ProcessId=$parent"; if(-not $p){break}; $script:ancestors += $p.Name; $script:ancestorPids += [int]$p.ProcessId; $parent=$p.ParentProcessId }
  if ($script:ancestors -notcontains 'sshd.exe') { throw 'sshd.exe ancestry absent' }
  Assert-Gui; Assert-Wts
  if ($BeforeDispatch) { Assert-RunAbsent }
  $other = @(Get-CimInstance Win32_Process -Filter "Name='Simlox.exe'" | Where-Object { $_.ProcessId -ne 13340 })
  if ($other.Count) { throw 'another SIMLOX process is active' }
  $currentSshTree = @([int]$PID) + @($script:ancestorPids); $runners = @(Get-CimInstance Win32_Process | Where-Object { $currentSshTree -notcontains [int]$_.ProcessId -and $_.SessionId -eq 0 -and $_.Name -match '^(powershell|pwsh|python|cmd)\.exe$' -and $_.CommandLine -match '(?i)i05-var05|run_native_ssh' })
  if ($runners.Count) { throw 'competing Issue 18 runner is active' }
  Assert-Sources $manifest
}
function Save-Closure([string]$errorText, $steps, [string]$mode) {
  $files = @{}
  if (Test-Path -LiteralPath $run -PathType Container) {
    Get-ChildItem -LiteralPath $run -File | ForEach-Object { $files[$_.Name] = [ordered]@{bytes=$_.Length;sha256=(Get-Sha $_.FullName)} }
  }
  [ordered]@{schema='i05-var05-native-closure/v1';run_id=$runId;mode=$mode;native_run_directory=$run;
    error=$errorText;steps=$steps;files=$files;publication_state='not_published'} |
    ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
}
function Save-Steps($steps) {
  ConvertTo-Json -InputObject $steps -Depth 10 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
}

if (-not (Test-Path -LiteralPath $workingDirectory -PathType Container) -or -not (Test-Path -LiteralPath $exe -PathType Leaf) -or -not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'SIMLOX executable, Python, or work directory absent' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.schema -ne 'i05-var05-prelaunch-manifest/v1' -or $manifest.run_id -cne $runId -or $manifest.native_run_directory -cne $run) { throw 'manifest identity mismatch' }
Assert-Environment $manifest -BeforeDispatch
$before = @{}; foreach ($entry in $manifest.source_files) { $before[$entry.key] = Get-Sha $entry.path }
$queue = New-Object System.Threading.Mutex($false, $mutexName)
$acquired = $false
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide native queue mutex is already owned' }
  Assert-Environment $manifest -BeforeDispatch
  if ($PreflightOnly) {
    $exeHash = Get-Sha $exe
    $path = Join-Path $case ('review\preflight-ssh0-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '.json')
    $receipt = [ordered]@{schema='i05-var05-ssh-preflight/v1';utc=[DateTime]::UtcNow.ToString('o');run_id=$runId;
      powershell_version=$PSVersionTable.PSVersion.ToString();session_id=0;ssh_connection_present=[bool]$env:SSH_CONNECTION;
      ssh_ancestors=$ancestors;ssh_ancestor_pids=$script:ancestorPids;host_name=$env:COMPUTERNAME;gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
      queue_mutex=$mutexName;mutex_owned_by_this_preflight=$true;native_run_directory=$run;run_path_absent=$true;
      manifest_sha256=(Get-Sha $manifestPath);
      accepted_parent_publication_id=$manifest.accepted_parent_publication.publication_id;
      publication_index_sha256=$manifest.live_publication_index_prelaunch_pin.sha256;
      simlox_exe_sha256=$exeHash;source_hashes=$before;native_dispatch=$false;publication_state='not_published'}
    $receiptJson = $receipt | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($path, $receiptJson + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))
    Write-Output $path
    return
  }
  $approval = Get-Content -LiteralPath $approvalPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($approval.schema -ne 'i05-var05-independent-prelaunch-go/v1' -or $approval.decision -ne 'GO_PRELAUNCH' -or
      $approval.run_id -cne $runId -or $approval.native_run_directory -cne $run -or
      $approval.manifest_sha256 -cne (Get-Sha $manifestPath) -or $approval.runner_sha256 -cne (Get-Sha $PSCommandPath)) {
    throw 'independent prelaunch approval does not bind these exact files and run'
  }
  $preflightPath = Join-Path $case $approval.preflight_relative_path
  if (-not (Test-Path -LiteralPath $preflightPath) -or (Get-Sha $preflightPath) -cne $approval.preflight_sha256) { throw 'fresh preflight receipt mismatch' }
  $preflight = Get-Content -LiteralPath $preflightPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($preflight.native_dispatch -ne $false -or $preflight.run_id -cne $runId -or $preflight.native_run_directory -cne $run -or
      $preflight.manifest_sha256 -cne (Get-Sha $manifestPath) -or
      $preflight.simlox_exe_sha256 -cne (Get-Sha $exe)) { throw 'preflight identity or native-dispatch flag differs' }
  $preflightTime = [DateTimeOffset]::Parse($preflight.utc).ToUniversalTime()
  if (([DateTimeOffset]::UtcNow - $preflightTime).TotalMinutes -gt 30 -or
      ([DateTimeOffset]::UtcNow - $preflightTime).TotalMinutes -lt -1) { throw 'preflight receipt is stale or future-dated' }
  foreach ($key in $before.Keys) {
    $pinned = $preflight.source_hashes.PSObject.Properties[$key]
    if (-not $pinned -or $pinned.Value -cne $before[$key]) { throw "preflight source hash differs: $key" }
  }
  if ($manifest.input_sha256 -cne $before['owned:native-input.json'] -or $manifest.contract_sha256 -cne $before['owned:contract.json']) { throw 'input/contract pin mismatch' }
  if (Test-Path -LiteralPath $run) { throw 'reserved run path appeared before dispatch' }
  New-Item -ItemType Directory -Path $run | Out-Null
  $steps = @(); $failure = $null
  try {
    $input = Join-Path $run 'input.json'; Copy-Item -LiteralPath (Join-Path $case 'native-input.json') -Destination $input
    if ((Get-Sha $input) -cne $manifest.input_sha256) { throw 'staged input hash mismatch' }
    $sxi=Join-Path $run 'model.sxi'; $sxo=Join-Path $run 'model.sxo'
    $commands = @(
      [ordered]@{name='import';args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $input,$sxi,(Join-Path $run 'import.log'))},
      [ordered]@{name='export';args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'export.log'))}
    )
    $invocation = [ordered]@{schema='i05-var05-native-invocation/v1';run_id=$runId;created_utc=[DateTime]::UtcNow.ToString('o');
      native_run_directory=$run;host_name=$env:COMPUTERNAME;session_id=0;ssh_ancestors=$ancestors;ssh_ancestor_pids=$script:ancestorPids;queue_mutex=$mutexName;
      gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true};
      input_sha256=(Get-Sha $input);contract_sha256=$manifest.contract_sha256;execution_contract_sha256=$manifest.execution_contract_sha256;
      manifest_sha256=(Get-Sha $manifestPath);approval_sha256=(Get-Sha $approvalPath);preflight_sha256=$approval.preflight_sha256;
      runner_sha256=(Get-Sha $PSCommandPath);transport_sha256=(Get-Sha (Join-Path $case 'ssh_transport.py'));
      simlox_exe_sha256=(Get-Sha $exe);parent_run_id=$manifest.parent_run_id;source_hashes_before=$before;
      planned_commands=$commands;publication_state='not_published'}
    $invocation | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
    Save-Steps $steps
    foreach ($command in $commands) {
      Assert-Environment $manifest
      $step=[ordered]@{name=$command.name;arguments=$command.args;started_utc=[DateTime]::UtcNow.ToString('o');completed_utc=$null;exit_code=$null;status='started'}; $steps += $step
      Save-Steps $steps
      $proc=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
      $step.exit_code=$proc.ExitCode; $step.completed_utc=[DateTime]::UtcNow.ToString('o')
      Assert-Environment $manifest
      if ($proc.ExitCode -ne 0) { throw "$($command.name) exit $($proc.ExitCode)" }
      $step.status='completed'
      Save-Steps $steps
    }
    $step=[ordered]@{name='check_roundtrip';arguments=@((Join-Path $case 'check_roundtrip.py'),$input,(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'import.log'),(Join-Path $run 'export.log'));started_utc=[DateTime]::UtcNow.ToString('o');completed_utc=$null;exit_code=$null;status='started'}; $steps += $step
    Save-Steps $steps
    & $python -X utf8 -B (Join-Path $case 'check_roundtrip.py') $input (Join-Path $run 'roundtrip-raw.json') (Join-Path $run 'import.log') (Join-Path $run 'export.log') | Set-Content -LiteralPath (Join-Path $run 'roundtrip-validation.json') -Encoding UTF8
    $step.exit_code=$LASTEXITCODE; $step.completed_utc=[DateTime]::UtcNow.ToString('o'); Assert-Environment $manifest
    if ($LASTEXITCODE -ne 0) { throw "roundtrip checker exit $LASTEXITCODE" }; $step.status='completed'
    Save-Steps $steps
    $calcArgs='"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'model-run.log')
    $step=[ordered]@{name='calc';arguments=$calcArgs;started_utc=[DateTime]::UtcNow.ToString('o');completed_utc=$null;exit_code=$null;status='started'}; $steps += $step
    Save-Steps $steps
    Assert-Environment $manifest; $proc=Start-Process -FilePath $exe -ArgumentList $calcArgs -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
    $step.exit_code=$proc.ExitCode; $step.completed_utc=[DateTime]::UtcNow.ToString('o'); Assert-Environment $manifest
    if ($proc.ExitCode -ne 0) { throw "calc exit $($proc.ExitCode)" }
    $converter=Get-Content -LiteralPath (Join-Path $run 'model-run.log') -Raw -Encoding UTF8
    if ($converter -notmatch 'Input conversion completed\. Errors: 0,' -or $converter -match '(?im)^.*\bErrors: [1-9]') { throw 'converter did not report zero errors' }
    $step.status='completed_zero_converter_errors'
    Save-Steps $steps
    if (-not (Test-Path -LiteralPath $sxo) -or (Get-Item $sxo).Length -le 4 -or -not (Test-Path (Join-Path $run 'model.log'))) { throw 'nonempty SXO or event log absent' }
    $reportArgs='"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,(Join-Path $run 'report-raw.json'),(Join-Path $run 'report-export.log')
    $step=[ordered]@{name='jsonreport';arguments=$reportArgs;started_utc=[DateTime]::UtcNow.ToString('o');completed_utc=$null;exit_code=$null;status='started'}; $steps += $step
    Save-Steps $steps
    Assert-Environment $manifest; $proc=Start-Process -FilePath $exe -ArgumentList $reportArgs -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
    $step.exit_code=$proc.ExitCode; $step.completed_utc=[DateTime]::UtcNow.ToString('o'); Assert-Environment $manifest
    if ($proc.ExitCode -ne 0 -or -not (Test-Path (Join-Path $run 'report-raw.json')) -or (Get-Item (Join-Path $run 'report-raw.json')).Length -le 4) { throw 'JSON report failed or empty' }
    $step.status='completed';
    Save-Steps $steps
    $step=[ordered]@{name='check_behavior';arguments=@((Join-Path $case 'validate_native_cli.py'),$run);started_utc=[DateTime]::UtcNow.ToString('o');completed_utc=$null;exit_code=$null;status='started'}; $steps += $step
    Save-Steps $steps
    & $python -X utf8 -B (Join-Path $case 'validate_native_cli.py') $run | Set-Content -LiteralPath (Join-Path $run 'behavior-validation.json') -Encoding UTF8
    $step.exit_code=$LASTEXITCODE; $step.completed_utc=[DateTime]::UtcNow.ToString('o'); Assert-Environment $manifest
    if ($LASTEXITCODE -ne 0) { throw "behavior checker exit $LASTEXITCODE" }; $step.status='completed'
    Save-Steps $steps
    Assert-Sources $manifest
  } catch { $failure=$_.Exception.Message }
  Save-Closure $failure $steps 'native'
  if ($failure) { throw $failure }
  [ordered]@{run_id=$runId;native_run_directory=$run;steps=$steps;publication_state='not_published'} | ConvertTo-Json -Depth 8
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

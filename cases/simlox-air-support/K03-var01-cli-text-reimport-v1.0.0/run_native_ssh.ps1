param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$run = Join-Path (Join-Path $case 'runs') $RunId
$parent = Join-Path (Split-Path $case -Parent) 'K03-var01-cli-text-export-v1.0.1'
$parentRun = Join-Path (Join-Path $parent 'runs') 'k03-var01-text-v101-ssh-20261004-01'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$sources = [ordered]@{
  contract = @((Join-Path $case 'contract.json'), '2e07ae8979000bbd3436c87c4792c67b4c9c2a95dc1c1d24c7c2be047feb0e7e')
  parent_text = @((Join-Path $parentRun 'model.txt'), 'a12424532b92c1f5f0b69dee595b7488f88ad71cabc270cfb08e90a52eeb38eb')
  parent_json = @((Join-Path $parentRun 'model-raw.json'), '7d3a6ebe5b9b1170dca1d8115555ebb26dc4c47c03cc325e4d6576bd921dc9e9')
  parent_closure = @((Join-Path $parentRun 'closure.json'), '19114d2e6877b4dd67ea9d2a4019527d6d6f973d19ff919f58f997113c690d73')
  parent_signoff = @((Join-Path $parent 'cli-scope-signoff-2026-10-04.md'), 'f2457b3e7a97e345b760275254d54b8e1af6f464ae01b58f6e052ce24feeaadb')
  exe = @($exe, 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual = @('C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf', '39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
}
function Assert-Gui {
  $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $script:guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $script:guiStart) { throw 'GUI process changed' }
}
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if ($RunId -ne 'k03-var01-reimport-v100-ssh-20261004-01') { throw 'run id differs from contract' }
if (Test-Path -LiteralPath $run) { throw 'immutable native run already exists' }
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned working directory absent' }
$ancestors = @(); $ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name; $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'cannot verify sshd ancestor' }
foreach ($entry in $sources.GetEnumerator()) {
  $path, $expected = $entry.Value
  if (-not (Test-Path -LiteralPath $path) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw "source fingerprint differs: $($entry.Key)" }
}
$contract = Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($contract.case_id -ne 'K03' -or $contract.variant_id -ne 'K03.var01' -or $contract.version -ne '1.0.0-candidate' -or $contract.run_id -ne $RunId -or $contract.accepted_parent.text_sha256 -ne $sources.parent_text[1] -or $contract.accepted_parent.closure_sha256 -ne $sources.parent_closure[1] -or $contract.parameters.delimiter -ne '!' -or $contract.parameters.width -ne 4096) { throw 'contract fields differ' }
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false; $runCreated = $false; $runSealed = $false; $fatalError = $null
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide native queue busy' }
  $gui = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -le 0) { throw 'expected GUI PID 13340 only' }
  $script:guiSession = $gui[0].SessionId; $script:guiStart = $gui[0].StartTime.ToUniversalTime().ToString('o')
  $sessions = @(qwinsta 2>&1)
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session not active' }
  New-Item -ItemType Directory -Path $run -Force | Out-Null; $runCreated = $true
  Copy-Item -LiteralPath (Join-Path $parentRun 'model.txt') -Destination (Join-Path $run 'input.txt')
  $sourceHashes = [ordered]@{}
  foreach ($entry in $sources.GetEnumerator()) { $sourceHashes[$entry.Key] = $entry.Value[1] }
  $sourceHashes['run_native_ssh.ps1'] = (Get-FileHash -LiteralPath (Join-Path $case 'run_native_ssh.ps1') -Algorithm SHA256).Hash.ToLowerInvariant()
  $sxi = Join-Path $run 'model.sxi'; $sxo = Join-Path $run 'model.sxo'
  $commands = @(
    [pscustomobject]@{name='timport';args=('-silent -timport "{0}" -twidth 4096 -tsep ! -save "{1}" -log "{2}" -close' -f (Join-Path $run 'input.txt'),$sxi,(Join-Path $run 'text-import.log'))},
    [pscustomobject]@{name='jexport';args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run 'roundtrip-raw.json'),(Join-Path $run 'json-export.log'))},
    [pscustomobject]@{name='calc';args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log'))},
    [pscustomobject]@{name='jsonreport';args=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,(Join-Path $run 'report-raw.json'),(Join-Path $run 'report-export.log'))}
  )
  [ordered]@{schema='simlox-k03-var01-reimport-native/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');original_run_dir=$run;execution_mode='ssh_cli_v1';session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$workingDirectory;planned_commands=@($commands | ForEach-Object {[ordered]@{name=$_.name;arguments=$_.args}});source_hashes_before=$sourceHashes;publication_state='not_published'} | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps = @(); $errorText = $null
  foreach ($command in $commands) {
    Write-Output "K03.var01 reimport native: $($command.name)"
    $step = [ordered]@{name=$command.name;arguments=$command.args;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;gui_preserved=$false;status='started';error=$null}
    $steps += $step
    try {
      Assert-Gui
      $process = Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
      $step.exit_code=$process.ExitCode; Assert-Gui; $step.gui_preserved=$true
      if ($process.ExitCode -ne 0) { throw "$($command.name) exit=$($process.ExitCode)" }
      $required = switch ($command.name) { 'timport' {@('model.sxi')} 'jexport' {@('roundtrip-raw.json','json-export.log')} 'calc' {@('model.sxo','run.log','model.log')} 'jsonreport' {@('report-raw.json','report-export.log')} }
      foreach ($name in $required) { $path=Join-Path $run $name; if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -le 4) { throw "$($command.name) output $name absent/empty" } }
      if ($command.name -eq 'calc') {
        $log=Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw -Encoding UTF8
        if ($log -notmatch 'Input conversion completed\. Errors: 0,' -or [regex]::IsMatch($log,'\(error #')) { throw 'converter rejection' }
      }
      $step.status='completed'
    } catch { $errorText=$_.Exception.Message; $step.status='failed'; $step.error=$errorText; break }
    finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
  }
  $sourceHashesAfter = [ordered]@{}
  foreach ($entry in $sources.GetEnumerator()) { $sourceHashesAfter[$entry.Key]=(Get-FileHash -LiteralPath $entry.Value[0] -Algorithm SHA256).Hash.ToLowerInvariant() }
  $sourceHashesAfter['run_native_ssh.ps1']=(Get-FileHash -LiteralPath (Join-Path $case 'run_native_ssh.ps1') -Algorithm SHA256).Hash.ToLowerInvariant()
  foreach ($key in $sourceHashes.Keys) { if ($sourceHashes[$key] -ne $sourceHashesAfter[$key]) { $errorText="source changed during run: $key" } }
  $raw=@{}; foreach ($file in Get-ChildItem -LiteralPath $run -File) { if ($file.Name -ne 'invocation.json') { $raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} } }
  [ordered]@{schema='simlox-k03-var01-reimport-native-closure/v1';run_id=$RunId;invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();source_hashes_before=$sourceHashes;source_hashes_after=$sourceHashesAfter;raw=$raw;error=$errorText;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $runSealed=$true; if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;native_steps='completed'} | ConvertTo-Json)
} catch { $fatalError=$_.Exception.Message; throw }
finally {
  if ($runCreated -and -not $runSealed -and -not (Test-Path -LiteralPath (Join-Path $run 'closure.json'))) {
    try {
      $partialRaw=@{}; foreach ($file in Get-ChildItem -LiteralPath $run -File) { if ($file.Name -ne 'invocation.json') { $partialRaw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} } }
      $invocationPath=Join-Path $run 'invocation.json'; $invocationSha=if(Test-Path -LiteralPath $invocationPath){(Get-FileHash -LiteralPath $invocationPath -Algorithm SHA256).Hash.ToLowerInvariant()}else{$null}
      [ordered]@{schema='simlox-k03-var01-reimport-native-closure/v1';run_id=$RunId;invocation_sha256=$invocationSha;source_hashes_before=$sourceHashes;source_hashes_after=$null;raw=$partialRaw;error=$fatalError;publication_state='excluded_diagnostic';partial=$true} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
    } catch { Write-Error "partial closure failed: $($_.Exception.Message)" }
  }
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }; $queue.Dispose()
}


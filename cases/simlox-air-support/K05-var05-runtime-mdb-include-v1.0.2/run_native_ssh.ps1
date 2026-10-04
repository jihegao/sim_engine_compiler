param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$run = Join-Path (Join-Path $case 'runs') $RunId
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$ps32 = 'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$parent = Join-Path (Split-Path $case -Parent) 'K02-var01-json-structure-v1.0.1'
$sources = [ordered]@{
  main_input = @((Join-Path $case 'main-input.json'), 'ed57d43da4315fcd2f4fbd5cd80840c2add42adf9227bcfc947ad99477575044')
  database_source = @((Join-Path $case 'database-source.json'), '2c2fc671f6084ce90a4635526e50dc6df4b7ebd087c8fd8eca4080839c5a3ddb')
  accepted_parent = @((Join-Path $parent 'named-input.json'), 'b94e367d46665d4d58f2fb8d15771a61a6d51369070db85ab9bda851c3e76b00')
  accepted_parent_closure = @((Join-Path $parent 'runs\k02-var01-named-v101-ssh-20261004-01\closure.json'), '86e93d3fc94dcae4b034432b2ccea16e84c7b3e17894d3e5ea6ef1bdb2b999c3')
  exe = @($exe, 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual = @('C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf', '39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
}
function Assert-Gui {
  $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $script:guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $script:guiStart) { throw 'GUI process changed' }
}
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if ($RunId -ne 'k05-var05-mdb-v102-ssh-20261004-01') { throw 'run id differs from frozen database path' }
if (Test-Path -LiteralPath $run) { throw 'immutable native run already exists' }
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned working directory absent' }
$ancestors = @()
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'cannot verify sshd ancestor' }
foreach ($entry in $sources.GetEnumerator()) {
  $path, $expected = $entry.Value
  if (-not (Test-Path -LiteralPath $path) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw "source fingerprint differs: $($entry.Key)" }
}
& $python (Join-Path $case 'build.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen builder check failed' }
$contract = Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($contract.case_id -ne 'K05' -or $contract.variant_id -ne 'K05.var05' -or $contract.version -ne '1.0.2-candidate' -or $contract.run_id -ne $RunId -or $contract.inputs_sha256.main -ne $sources.main_input[1] -or $contract.inputs_sha256.database_source -ne $sources.database_source[1] -or $contract.dependency.closure_sha256 -ne $sources.accepted_parent_closure[1]) { throw 'contract fields differ' }
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false; $runCreated = $false; $runSealed = $false; $fatalError = $null
$associationPath = 'HKCU:\Software\Systecon\SIMLOX Version 2017\Database Associations'
$associationOriginal = 'mdb=Microsoft Access Driver (*.mdb)|'
$associationTemporary = 'mdb=Microsoft Access Driver (*.mdb, *.accdb)|'
$associationChanged = $false
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide native queue busy' }
  $gui = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -le 0) { throw 'expected GUI PID 13340 only' }
  $script:guiSession = $gui[0].SessionId
  $script:guiStart = $gui[0].StartTime.ToUniversalTime().ToString('o')
  $sessions = @(qwinsta 2>&1)
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session not active' }
  if ((Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations) -cne $associationOriginal) { throw 'database association differs from frozen prerequisite' }
  $mainDoc = Get-Content -LiteralPath (Join-Path $case 'main-input.json') -Raw -Encoding UTF8 | ConvertFrom-Json
  $includeTable = @($mainDoc.model.tables | Where-Object {$_.name -eq 'IncludeFiles'})
  if ($includeTable.Count -ne 1 -or $includeTable[0].instances[0].rows[0][0] -ne (Join-Path $run 'included.mdb')) { throw 'include path differs from frozen run' }
  New-Item -ItemType Directory -Path $run -Force | Out-Null
  $runCreated = $true
  Copy-Item -LiteralPath (Join-Path $case 'main-input.json') -Destination (Join-Path $run 'main-input.json')
  Copy-Item -LiteralPath (Join-Path $case 'database-source.json') -Destination (Join-Path $run 'database-source.json')
  $sourceHashes = [ordered]@{}
  foreach ($entry in $sources.GetEnumerator()) { $sourceHashes[$entry.Key] = $entry.Value[1] }
  foreach ($name in @('build.py','create_mdb_x86.ps1','run_native_ssh.ps1','contract.json')) { $sourceHashes[$name] = (Get-FileHash -LiteralPath (Join-Path $case $name) -Algorithm SHA256).Hash.ToLowerInvariant() }
  $sourceHashes.python = (Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant()
  $sourceHashes.powershell_x86 = (Get-FileHash -LiteralPath $ps32 -Algorithm SHA256).Hash.ToLowerInvariant()
  $database = Join-Path $run 'included.mdb'; $sxi = Join-Path $run 'model.sxi'; $sxo = Join-Path $run 'model.sxo'
  $commands = @(
    [pscustomobject]@{ name='database_create'; args=@('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $case 'create_mdb_x86.ps1'),'-Source',(Join-Path $run 'database-source.json'),'-Output',$database) },
    [pscustomobject]@{ name='main_import'; args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'main-input.json'),$sxi,(Join-Path $run 'main-import.log')) },
    [pscustomobject]@{ name='main_export'; args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run 'main-roundtrip-raw.json'),(Join-Path $run 'main-export.log')) },
    [pscustomobject]@{ name='calc'; args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log')) },
    [pscustomobject]@{ name='jsonreport'; args=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,(Join-Path $run 'report-raw.json'),(Join-Path $run 'report-export.log')) }
  )
  [ordered]@{schema='simlox-k05-var05-native/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');original_run_dir=$run;execution_mode='ssh_cli_v1';session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';working_directory=$workingDirectory;database_association_before=$associationOriginal;database_association_during_calc=$associationTemporary;planned_commands=@($commands | ForEach-Object { [ordered]@{name=$_.name;arguments=$_.args} });source_hashes_before=$sourceHashes;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps = @(); $errorText = $null
  foreach ($command in $commands) {
    Write-Output "K05.var05 native: $($command.name)"
    $step = [ordered]@{name=$command.name;arguments=$command.args;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;gui_preserved=$false;status='started';error=$null}
    $steps += $step
    try {
      Assert-Gui
      if ($command.name -eq 'database_create') {
        & $ps32 @($command.args)
        $step.exit_code = $LASTEXITCODE
      } elseif ($command.name -eq 'calc') {
        try {
          Set-ItemProperty -LiteralPath $associationPath -Name ListOfAssociations -Value $associationTemporary
          $associationChanged = $true
          if ((Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations) -cne $associationTemporary) { throw 'temporary association did not apply' }
          $process = Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
          $step.exit_code = $process.ExitCode
        } finally {
          if ($associationChanged) {
            Set-ItemProperty -LiteralPath $associationPath -Name ListOfAssociations -Value $associationOriginal
            $associationChanged = $false
            if ((Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations) -cne $associationOriginal) { throw 'database association restore failed' }
          }
        }
      } else {
        $process = Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
        $step.exit_code = $process.ExitCode
      }
      Assert-Gui; $step.gui_preserved = $true
      if ($step.exit_code -ne 0) { throw "$($command.name) exit=$($step.exit_code)" }
      $required = switch ($command.name) { 'database_create' {@('included.mdb','included.readback.json')} 'main_import' {@('model.sxi','main-import.log')} 'main_export' {@('main-roundtrip-raw.json','main-export.log')} 'calc' {@('model.sxo','run.log','model.log')} 'jsonreport' {@('report-raw.json','report-export.log')} }
      foreach ($name in $required) { $path = Join-Path $run $name; if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -le 4) { throw "$($command.name) output $name absent/empty" } }
      if ($command.name -eq 'calc') {
        $log = Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw -Encoding UTF8
        if ($log -notmatch 'Input conversion completed\. Errors: 0,' -or [regex]::IsMatch($log, '\(error #')) { throw 'converter rejection' }
      }
      $step.status='completed'
    } catch { $errorText=$_.Exception.Message; $step.status='failed'; $step.error=$errorText; break }
    finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
  }
  $sourceHashesAfter = [ordered]@{}
  foreach ($entry in $sources.GetEnumerator()) { $sourceHashesAfter[$entry.Key] = (Get-FileHash -LiteralPath $entry.Value[0] -Algorithm SHA256).Hash.ToLowerInvariant() }
  foreach ($name in @('build.py','create_mdb_x86.ps1','run_native_ssh.ps1','contract.json')) { $sourceHashesAfter[$name] = (Get-FileHash -LiteralPath (Join-Path $case $name) -Algorithm SHA256).Hash.ToLowerInvariant() }
  $sourceHashesAfter.python = (Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant()
  $sourceHashesAfter.powershell_x86 = (Get-FileHash -LiteralPath $ps32 -Algorithm SHA256).Hash.ToLowerInvariant()
  foreach ($key in $sourceHashes.Keys) { if ($sourceHashes[$key] -ne $sourceHashesAfter[$key]) { $errorText = "source changed during run: $key" } }
  $raw = @{}
  foreach ($file in Get-ChildItem -LiteralPath $run -File) { if ($file.Name -ne 'invocation.json') { $raw[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} } }
  [ordered]@{schema='simlox-k05-var05-native-closure/v1';run_id=$RunId;invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();source_hashes_before=$sourceHashes;source_hashes_after=$sourceHashesAfter;database_association_after=(Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations);raw=$raw;error=$errorText;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $runSealed = $true
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;native_steps='completed'} | ConvertTo-Json)
} catch { $fatalError = $_.Exception.Message; throw }
finally {
  if ($associationChanged) {
    try { Set-ItemProperty -LiteralPath $associationPath -Name ListOfAssociations -Value $associationOriginal; $associationChanged = $false } catch { Write-Error "emergency database association restore failed: $($_.Exception.Message)" }
  }
  if ($runCreated -and -not $runSealed -and -not (Test-Path -LiteralPath (Join-Path $run 'closure.json'))) {
    try {
      $partialRaw = @{}
      foreach ($file in Get-ChildItem -LiteralPath $run -File) { if ($file.Name -ne 'invocation.json') { $partialRaw[$file.Name] = [ordered]@{bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} } }
      $invocationPath = Join-Path $run 'invocation.json'
      $invocationSha = if (Test-Path -LiteralPath $invocationPath) { (Get-FileHash -LiteralPath $invocationPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
      [ordered]@{schema='simlox-k05-var05-native-closure/v1';run_id=$RunId;invocation_sha256=$invocationSha;source_hashes_before=$sourceHashes;source_hashes_after=$null;raw=$partialRaw;error=$fatalError;publication_state='excluded_diagnostic';partial=$true} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
    } catch { Write-Error "partial closure failed: $($_.Exception.Message)" }
  }
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

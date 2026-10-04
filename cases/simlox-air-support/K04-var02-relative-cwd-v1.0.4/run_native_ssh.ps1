param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId)
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$run = Join-Path (Join-Path $case 'runs') $RunId
$parent = Join-Path (Split-Path $case -Parent) 'K04-var01-nested-mdb-include-v1.0.0'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual = 'C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$ps32 = 'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
$negativeCwd = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$associationPath = 'HKCU:\Software\Systecon\SIMLOX Version 2017\Database Associations'
$associationOriginal = 'mdb=Microsoft Access Driver (*.mdb)|'
$associationTemporary = 'mdb=Microsoft Access Driver (*.mdb, *.accdb)|'
$sources = [ordered]@{
  main_input = @((Join-Path $case 'main-input.json'), '986316de56ee3ceb4503137a2c788204a44a89fde3cf84d9c85cc562b2e05d7f')
  level1_source = @((Join-Path $case 'level1-source.json'), '9e6a9a154b1051697a773c4bc14a3fb9160b0a1e1682911420f9a5020e7d5737')
  level2_source = @((Join-Path $case 'level2-source.json'), '2c2fc671f6084ce90a4635526e50dc6df4b7ebd087c8fd8eca4080839c5a3ddb')
  contract = @((Join-Path $case 'contract.json'), '043a6a84affed309c3437cd4cbb234e7c7bec3e37a39912fc12ad977ff40bdec')
  accepted_parent_main = @((Join-Path $parent 'main-input.json'), 'aa0064561c2a1aa9738422c8090ca125478c0517e16010022634bd985da6fa52')
  accepted_parent_level1 = @((Join-Path $parent 'level1-source.json'), '4b2d888f039ce6303cd9fc86bc35c00c84939d433e4cbc87444907f3d5992f23')
  accepted_parent_level2 = @((Join-Path $parent 'level2-source.json'), '2c2fc671f6084ce90a4635526e50dc6df4b7ebd087c8fd8eca4080839c5a3ddb')
  accepted_parent_closure = @((Join-Path $parent 'runs\k04-var01-nested-mdb-v100-ssh-20261004-01\closure.json'), 'e8530f8e5cd65f788b70596e5f755f0b84ae350b66b7cff8746de36f23e3c0d0')
  accepted_parent_signoff = @((Join-Path $parent 'cli-scope-signoff-2026-10-04.md'), 'b508239bff323d4155bfb5ec10f3e8e3921d30e7ed6720cc5d42ce5b14d9d4ee')
  level1_generator = @((Join-Path $parent 'create_level1_mdb_x86.ps1'), '121123dc0758ecf7d992ce5a124b6dde969fc2678d7ecd5793e7b69434562627')
  level2_generator = @((Join-Path $parent 'create_level2_mdb_x86.ps1'), '5ad35afcfbd54691839820ccbc0b12d8da32fffc2076315ab574c116a85c1bbf')
  exe = @($exe, 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0')
  manual = @($manual, '39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3')
}
function Hash([string]$path) { return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Assert-Gui {
  $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $script:guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $script:guiStart) { throw 'GUI process changed' }
}
function Run-Simlox([string]$name,[string]$argumentLine,[string]$cwd,[bool]$useMdb) {
  $step = [ordered]@{name=$name;arguments=$argumentLine;working_directory=$cwd;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;gui_preserved=$false;status='started';error=$null}
  $script:steps += $step
  try {
    Assert-Gui
    if ($useMdb) {
      $script:associationChanged = $true
      Set-ItemProperty -LiteralPath $associationPath -Name ListOfAssociations -Value $associationTemporary
      if ((Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations) -cne $associationTemporary) { throw 'temporary MDB association did not apply' }
    }
    $proc = Start-Process -FilePath $exe -ArgumentList $argumentLine -WorkingDirectory $cwd -WindowStyle Hidden -PassThru -Wait
    $step.exit_code = $proc.ExitCode
    if ($useMdb) {
      Set-ItemProperty -LiteralPath $associationPath -Name ListOfAssociations -Value $associationOriginal
      $script:associationChanged = $false
      if ((Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations) -cne $associationOriginal) { throw 'MDB association restore failed' }
    }
    Assert-Gui; $step.gui_preserved = $true
    if ($step.exit_code -ne 0) { throw "$name exit=$($step.exit_code)" }
    $step.status='completed'
  } catch {
    $step.status='failed'; $step.error=$_.Exception.Message
    throw
  } finally {
    if ($script:associationChanged) {
      Set-ItemProperty -LiteralPath $associationPath -Name ListOfAssociations -Value $associationOriginal
      $script:associationChanged = $false
    }
    $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o')
    ConvertTo-Json -InputObject $script:steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
  }
}
function Run-Generator([string]$name,[string]$scriptPath,[string]$source,[string]$output) {
  $step = [ordered]@{name=$name;arguments=@('-NoProfile','-ExecutionPolicy','Bypass','-File',$scriptPath,'-Source',$source,'-Output',$output);working_directory=$run;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;gui_preserved=$false;status='started';error=$null}
  $script:steps += $step
  try {
    Assert-Gui
    & $ps32 @($step.arguments)
    $step.exit_code = $LASTEXITCODE
    Assert-Gui; $step.gui_preserved = $true
    if ($step.exit_code -ne 0) { throw "$name exit=$($step.exit_code)" }
    if ((Get-Item -LiteralPath $output).Length -le 4) { throw "$name database empty" }
    $step.status='completed'
  } catch { $step.status='failed'; $step.error=$_.Exception.Message; throw }
  finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $script:steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
}
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if ($RunId -ne 'k04-var02-relative-cwd-v104-ssh-20261004-01') { throw 'run id differs from frozen paths' }
if (Test-Path -LiteralPath $run) { throw 'immutable native run already exists' }
if (-not (Test-Path -LiteralPath $negativeCwd) -or (Test-Path -LiteralPath (Join-Path $negativeCwd 'level1.mdb')) -or (Test-Path -LiteralPath (Join-Path (Split-Path $exe -Parent) 'level1.mdb'))) { throw 'negative working directory prerequisite differs' }
$ancestors = @(); $ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name; $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'cannot verify sshd ancestor' }
foreach ($entry in $sources.GetEnumerator()) {
  $path, $expected = $entry.Value
  if (-not (Test-Path -LiteralPath $path) -or (Hash $path) -ne $expected) { throw "source fingerprint differs: $($entry.Key)" }
}
& $python (Join-Path $case 'build.py') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen builder failed' }
$contract = Get-Content -LiteralPath (Join-Path $case 'contract.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($contract.variant_id -ne 'K04.var02' -or $contract.run_id -ne $RunId -or $contract.negative_working_directory -cne $negativeCwd -or $contract.dependency.closure_sha256 -ne $sources.accepted_parent_closure[1] -or $contract.dependency.signoff_sha256 -ne $sources.accepted_parent_signoff[1] -or $contract.inputs_sha256.main -ne $sources.main_input[1] -or $contract.inputs_sha256.level1_source -ne $sources.level1_source[1] -or $contract.inputs_sha256.level2_source -ne $sources.level2_source[1]) { throw 'contract fields differ' }
$mainDoc = Get-Content -LiteralPath (Join-Path $case 'main-input.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$include = @($mainDoc.model.tables | Where-Object {$_.name -eq 'IncludeFiles'})
if ($include.Count -ne 1 -or $include[0].instances[0].rows[0][0] -cne 'level1.mdb') { throw 'relative include input differs' }
$level1Doc = Get-Content -LiteralPath (Join-Path $case 'level1-source.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($level1Doc.rows[0][0] -cne (Join-Path $run 'level2.mdb')) { throw 'absolute nested include differs' }
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired=$false; $runCreated=$false; $runSealed=$false; $associationChanged=$false; $fatalError=$null; $steps=@()
try {
  try { $acquired=$queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired=$true }
  if (-not $acquired) { throw 'host-wide native queue busy' }
  $gui=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -le 0) { throw 'expected GUI PID 13340 only' }
  $script:guiSession=$gui[0].SessionId; $script:guiStart=$gui[0].StartTime.ToUniversalTime().ToString('o')
  $sessions=@(qwinsta 2>&1)
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session not active' }
  if ((Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations) -cne $associationOriginal) { throw 'MDB association differs' }
  New-Item -ItemType Directory -Path $run -Force | Out-Null; $runCreated=$true
  foreach ($name in @('main-input.json','level1-source.json','level2-source.json')) { Copy-Item -LiteralPath (Join-Path $case $name) -Destination (Join-Path $run $name) }
  $sourceHashes=[ordered]@{}
  foreach ($entry in $sources.GetEnumerator()) { $sourceHashes[$entry.Key]=$entry.Value[1] }
  foreach ($name in @('build.py','run_native_ssh.ps1')) { $sourceHashes[$name]=Hash (Join-Path $case $name) }
  $sourceHashes.python=Hash $python; $sourceHashes.powershell_x86=Hash $ps32
  $sxi=Join-Path $run 'model.sxi'; $sxo=Join-Path $run 'model.sxo'
  $level1=Join-Path $run 'level1.mdb'; $level2=Join-Path $run 'level2.mdb'
  [ordered]@{schema='simlox-k04-var02-relative-cwd-native/ssh-cli-v1';run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');original_run_dir=$run;execution_mode='ssh_cli_v1';session_id=0;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';first_working_directory=$run;alternate_working_directory=$negativeCwd;database_association_before=$associationOriginal;database_association_during_calc=$associationTemporary;source_hashes_before=$sourceHashes;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $errorText=$null
  try {
    Write-Output 'K04.var02 native: create nested MDBs'
    Run-Generator 'level2_create' $sources.level2_generator[0] (Join-Path $run 'level2-source.json') $level2
    Run-Generator 'level1_create' $sources.level1_generator[0] (Join-Path $run 'level1-source.json') $level1
    foreach ($name in @('level1.readback.json','level2.readback.json')) { if ((Get-Item -LiteralPath (Join-Path $run $name)).Length -le 4) { throw "readback missing: $name" } }
    Write-Output 'K04.var02 native: import/export one relative-path SXI'
    Run-Simlox 'main_import' ('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f (Join-Path $run 'main-input.json'),$sxi,(Join-Path $run 'main-import.log')) $negativeCwd $false
    Run-Simlox 'main_export' ('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,(Join-Path $run 'main-roundtrip-raw.json'),(Join-Path $run 'main-export.log')) $negativeCwd $false
    if ((Get-Item -LiteralPath $sxi).Length -le 4 -or (Get-Item -LiteralPath (Join-Path $run 'main-roundtrip-raw.json')).Length -le 4) { throw 'main SXI/roundtrip empty' }
    $roundtrip=Get-Content -LiteralPath (Join-Path $run 'main-roundtrip-raw.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $roundtripInclude=@($roundtrip.model.tables | Where-Object {$_.name -eq 'IncludeFiles'})
    if ($roundtripInclude.Count -ne 1 -or $roundtripInclude[0].instances[0].rows[0][0] -cne 'level1.mdb') { throw 'relative path not retained in SXI roundtrip' }
    $sxiSha=Hash $sxi
    Write-Output 'K04.var02 native: positive calculation'
    Run-Simlox 'positive_calc' ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'positive-run.log')) $run $true
    if ((Get-Item -LiteralPath $sxo).Length -le 4 -or (Get-Item -LiteralPath (Join-Path $run 'model.log')).Length -le 4) { throw 'positive calculation output empty' }
    $positiveLog=Get-Content -LiteralPath (Join-Path $run 'positive-run.log') -Raw -Encoding UTF8
    $level1Text=$level1.Replace('\','/'); $level2Text=$level2.Replace('\','/')
    if ($positiveLog -notmatch 'Input conversion completed\. Errors: 0,' -or [regex]::IsMatch($positiveLog,'\(error #') -or $positiveLog.IndexOf($level1Text) -lt 0 -or $positiveLog.IndexOf($level2Text) -le $positiveLog.IndexOf($level1Text) -or $positiveLog -notmatch 'Station, 1 record inserted') { throw 'positive nested include/converter rejected' }
    Run-Simlox 'positive_jsonreport' ('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,(Join-Path $run 'positive-report-raw.json'),(Join-Path $run 'positive-report-export.log')) $negativeCwd $false
    if ((Get-Item -LiteralPath (Join-Path $run 'positive-report-raw.json')).Length -le 4) { throw 'positive report empty' }
    Copy-Item -LiteralPath $sxo -Destination (Join-Path $run 'positive-model.sxo')
    Copy-Item -LiteralPath (Join-Path $run 'model.log') -Destination (Join-Path $run 'positive-model.log')
    Write-Output 'K04.var02 native: alternate process working directory, same SXI'
    if ((Hash $sxi) -ne $sxiSha) { throw 'SXI changed before alternate arm' }
    Run-Simlox 'alternate_calc' ('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'alternate-run.log')) $negativeCwd $true
    if ((Hash $sxi) -ne $sxiSha -or (Get-Item -LiteralPath $sxo).Length -le 4) { throw 'alternate SXI changed or output empty' }
    Copy-Item -LiteralPath $sxo -Destination (Join-Path $run 'alternate-model.sxo')
    Copy-Item -LiteralPath (Join-Path $run 'model.log') -Destination (Join-Path $run 'alternate-model.log')
    $alternateLog=Get-Content -LiteralPath (Join-Path $run 'alternate-run.log') -Raw -Encoding UTF8
    if ($alternateLog -notmatch 'Input conversion completed\. Errors: 0,' -or $alternateLog.IndexOf($level1Text) -lt 0 -or $alternateLog.IndexOf($level2Text) -le $alternateLog.IndexOf($level1Text) -or [regex]::IsMatch($alternateLog,'\(error #')) { throw 'alternate process cwd changed include resolution' }
    Run-Simlox 'alternate_jsonreport' ('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,(Join-Path $run 'alternate-report-raw.json'),(Join-Path $run 'alternate-report-export.log')) $negativeCwd $false
    if ((Get-Item -LiteralPath (Join-Path $run 'alternate-report-raw.json')).Length -le 4) { throw 'alternate report empty' }
    if ((Hash (Join-Path $run 'positive-model.log')) -ne (Hash (Join-Path $run 'alternate-model.log')) -or (Hash (Join-Path $run 'positive-report-raw.json')) -ne (Hash (Join-Path $run 'alternate-report-raw.json'))) { throw 'paired event/report parity differs' }
  } catch { $errorText=$_.Exception.Message }
  $sourceHashesAfter=[ordered]@{}
  foreach ($entry in $sources.GetEnumerator()) { $sourceHashesAfter[$entry.Key]=Hash $entry.Value[0] }
  foreach ($name in @('build.py','run_native_ssh.ps1')) { $sourceHashesAfter[$name]=Hash (Join-Path $case $name) }
  $sourceHashesAfter.python=Hash $python; $sourceHashesAfter.powershell_x86=Hash $ps32
  foreach ($key in $sourceHashes.Keys) { if ($sourceHashes[$key] -ne $sourceHashesAfter[$key]) { $errorText="source changed during run: $key" } }
  $raw=@{}
  foreach ($file in Get-ChildItem -LiteralPath $run -Recurse -File) { $relative=$file.FullName.Substring($run.Length+1).Replace('\','/'); if ($relative -ne 'invocation.json') { $raw[$relative]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName} } }
  [ordered]@{schema='simlox-k04-var02-relative-cwd-native-closure/v1';run_id=$RunId;invocation_sha256=Hash (Join-Path $run 'invocation.json');source_hashes_before=$sourceHashes;source_hashes_after=$sourceHashesAfter;database_association_after=(Get-ItemPropertyValue -LiteralPath $associationPath -Name ListOfAssociations);sxi_sha256=if (Test-Path -LiteralPath $sxi) {Hash $sxi} else {$null};raw=$raw;error=$errorText;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  $runSealed=$true
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{run_id=$RunId;run_dir=$run;native_steps='completed'} | ConvertTo-Json)
} catch { $fatalError=$_.Exception.Message; throw }
finally {
  if ($associationChanged) { try { Set-ItemProperty -LiteralPath $associationPath -Name ListOfAssociations -Value $associationOriginal } catch { Write-Error "emergency association restore failed: $($_.Exception.Message)" } }
  if ($runCreated -and -not $runSealed -and -not (Test-Path -LiteralPath (Join-Path $run 'closure.json'))) {
    $partialRaw=@{}
    foreach ($file in Get-ChildItem -LiteralPath $run -Recurse -File) { $relative=$file.FullName.Substring($run.Length+1).Replace('\','/'); if ($relative -ne 'invocation.json') { $partialRaw[$relative]=[ordered]@{bytes=$file.Length;sha256=Hash $file.FullName} } }
    [ordered]@{schema='simlox-k04-var02-relative-cwd-native-closure/v1';run_id=$RunId;raw=$partialRaw;error=$fatalError;publication_state='excluded_diagnostic';partial=$true} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  }
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

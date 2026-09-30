param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId
)
[IO.File]::WriteAllText("C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\A08-var04-same-time-iper-zero-v1.0.0\runs\preflight-trace-$RunId.txt", "entered script`r`n")
$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$run = Join-Path (Join-Path $case 'runs') $RunId
$base = Join-Path $case 'native-input.json'
$manifestPath = Join-Path $case 'seed-matrix-v1.json'
$initialContract = Join-Path $case 'contract.json'
$matrixContract = Join-Path $case 'contract-seed-matrix-v1.json'
$builder = Join-Path $case 'build.py'
$seedBuilder = Join-Path $case 'build_seed_matrix.py'
$checker = Join-Path $case 'check_roundtrip.py'
$seedChecker = Join-Path $case 'check_seed_roundtrip.py'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe = 'C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$workingDirectory = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$baseSha = 'bae76ba5a88871129fb2669a8d04744745b8831f11d0dec96c7594d621793485'
$manifestSha = 'ce971c2ff06054752e272feffd4e78a09102052e0903c6cb64b8cdd155af1348'
$seedBuilderSha = '3cb251644a73b2c9698fa55698c638e7ce5b5037dc34c8250a4490b094baa23c'
$exeSha = 'fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
$runnerPath = $PSCommandPath

function Hash([string]$path) { return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Source-Hashes {
  return [ordered]@{
    aggregate_input = (Hash $base)
    seed_manifest = (Hash $manifestPath)
    initial_contract = (Hash $initialContract)
    matrix_contract = (Hash $matrixContract)
    builder = (Hash $builder)
    seed_builder = (Hash $seedBuilder)
    checker = (Hash $checker)
    seed_checker = (Hash $seedChecker)
    python = (Hash $python)
    runner_script = (Hash $runnerPath)
    simlox_exe = (Hash $exe)
  }
}

Write-Output 'A08.var04 seed matrix preflight: session and fingerprints'
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if (Test-Path -LiteralPath $run) { throw 'immutable native matrix run already exists' }
$trace = Join-Path (Join-Path $case 'runs') ("preflight-trace-$RunId.txt")
function Trace([string]$phase) { [IO.File]::AppendAllText($trace, "$(Get-Date -Format o) $phase`r`n") }
Trace 'session guard passed'
$ancestors = @()
$ancestorPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) {
  $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"
  if (-not $ancestor) { break }
  $ancestors += $ancestor.Name
  $ancestorPid = $ancestor.ParentProcessId
}
if ($ancestors -notcontains 'sshd.exe') { throw 'cannot verify sshd ancestor' }
Trace 'sshd ancestor verified'
foreach ($path in @($base,$manifestPath,$initialContract,$matrixContract,$builder,$seedBuilder,$checker,$seedChecker,$python,$exe)) {
  if (-not (Test-Path -LiteralPath $path)) { throw "required source absent: $path" }
}
if ((Hash $base) -ne $baseSha -or (Hash $manifestPath) -ne $manifestSha -or (Hash $seedBuilder) -ne $seedBuilderSha -or (Hash $exe) -ne $exeSha) { throw 'pinned source or executable fingerprint differs' }
Trace 'source files and pinned hashes verified'
if (-not (Test-Path -LiteralPath $workingDirectory)) { throw 'pinned native working directory absent' }
& $python $builder | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen aggregate builder check failed' }
Trace 'aggregate builder passed'
& $python $seedBuilder --write-inputs | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'frozen seed matrix generation failed' }
Trace 'seed inputs generated'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.seeds.Count -ne 32 -or $manifest.parent_input_sha256 -ne $baseSha) { throw 'seed manifest structure differs' }
for ($i=0; $i -lt 32; $i++) {
  $item = $manifest.seeds[$i]
  if ($item.seed -ne ($i+1) -or $item.input_name -ne ('seed-{0:D2}.json' -f ($i+1))) { throw 'seed order differs' }
  $source = Join-Path (Join-Path $case 'seed-inputs') $item.input_name
  if (-not (Test-Path -LiteralPath $source) -or (Hash $source) -ne $item.input_sha256) { throw "seed input fingerprint differs: $($item.seed)" }
}
Trace '32 seed input hashes verified'
$sourceBefore = Source-Hashes
Trace 'source hashes before captured'

Write-Output 'A08.var04 seed matrix preflight: host queue and GUI identity'
$queue = [System.Threading.Mutex]::new($false, 'Global\SimloxIssue18NativeQueue')
$acquired = $false
try {
  try { $acquired = $queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $acquired = $true }
  if (-not $acquired) { throw 'host-wide Issue 18 native queue busy' }
  Trace 'host mutex acquired'
  $existing = @(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($existing.Count -ne 1 -or $existing[0].Id -ne 13340 -or $existing[0].SessionId -le 0) { throw 'expected existing GUI PID 13340 only' }
  $guiStart = $existing[0].StartTime.ToUniversalTime().ToString('o')
  $guiSession = $existing[0].SessionId
  $sessions = @(qwinsta 2>&1)
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session not active' }
  Trace 'GUI process and active session verified'
  function Assert-Gui {
    $p = @(Get-Process Simlox -ErrorAction SilentlyContinue)
    if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'GUI process changed' }
  }
  New-Item -ItemType Directory -Path $run -Force | Out-Null
  Trace 'run directory created'
  $invocation = [ordered]@{
    schema = 'simlox-a08-var04-seed-matrix-v1/ssh-cli-v1'
    run_id = $RunId; created_utc = (Get-Date).ToUniversalTime().ToString('o')
    original_run_dir = $run; host_name = $env:COMPUTERNAME
    execution_mode = 'ssh_cli_seed_matrix_v1'; session_id = (Get-Process -Id $PID).SessionId
    ssh_connection_present = [bool]$env:SSH_CONNECTION; ssh_ancestor_names = $ancestors
    gui = [ordered]@{ pid=13340; session_id=$guiSession; start_utc=$guiStart }
    queue_mutex = 'Global\SimloxIssue18NativeQueue'
    working_directory = $workingDirectory; source_hashes_before = $sourceBefore
    seeds = @($manifest.seeds | ForEach-Object { [ordered]@{ seed=$_.seed; input_name=$_.input_name; input_sha256=$_.input_sha256 } })
    scope = 'serial_32_seed_native_candidate'; publication_state = 'not_published'
  }
  $invocation | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps = @()
  $errorText = $null
  try {
    foreach ($item in $manifest.seeds) {
      $seedName = 'seed-{0:D2}' -f [int]$item.seed
      $sub = Join-Path $run $seedName
      New-Item -ItemType Directory -Path $sub -Force | Out-Null
      $source = Join-Path (Join-Path $case 'seed-inputs') $item.input_name
      Copy-Item -LiteralPath $source -Destination (Join-Path $sub 'input.json')
      if ((Hash (Join-Path $sub 'input.json')) -ne $item.input_sha256) { throw "copied input differs: $seedName" }
      $input = Join-Path $sub 'input.json'
      $sxi = Join-Path $sub 'model.sxi'
      $sxo = Join-Path $sub 'model.sxo'
      $round = Join-Path $sub 'roundtrip-raw.json'
      $report = Join-Path $sub 'report-raw.json'
      $commands = @(
        [pscustomobject]@{ name='import'; args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $input,$sxi,(Join-Path $sub 'import.log')) },
        [pscustomobject]@{ name='export'; args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,$round,(Join-Path $sub 'export.log')) },
        [pscustomobject]@{ name='calc'; args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $sub 'run.log')) },
        [pscustomobject]@{ name='jsonreport'; args=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,$report,(Join-Path $sub 'report-export.log')) }
      )
      foreach ($command in $commands) {
        $step = [ordered]@{ seed=$item.seed; name=$command.name; arguments=$command.args; started_utc=(Get-Date).ToUniversalTime().ToString('o'); completed_utc=$null; exit_code=$null; gui_preserved=$false; status='started'; error=$null }
        $steps += $step
        try {
          Assert-Gui
          $process = Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $workingDirectory -WindowStyle Hidden -PassThru -Wait
          $step.exit_code = $process.ExitCode
          Assert-Gui
          $step.gui_preserved = $true
          if ($process.ExitCode -ne 0) { throw "$seedName $($command.name) exit=$($process.ExitCode)" }
          $required = switch ($command.name) {
            'import' { @('model.sxi','import.log') }
            'export' { @('roundtrip-raw.json','export.log') }
            'calc' { @('model.sxo','run.log','model.log') }
            'jsonreport' { @('report-raw.json','report-export.log') }
          }
          foreach ($name in $required) {
            $output = Join-Path $sub $name
            if (-not (Test-Path -LiteralPath $output) -or (Get-Item -LiteralPath $output).Length -le 4) { throw "$seedName $($command.name) output $name absent/empty" }
          }
          $step.status = 'completed'
        } catch {
          $step.status = 'failed'; $step.error = $_.Exception.Message
          throw
        } finally {
          $step.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
          ConvertTo-Json -InputObject $steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
        }
      }
      $step = [ordered]@{ seed=$item.seed; name='check_import_export'; arguments=@($seedChecker,$sub,$item.input_sha256); started_utc=(Get-Date).ToUniversalTime().ToString('o'); completed_utc=$null; exit_code=$null; gui_preserved=$false; status='started'; error=$null }
      $steps += $step
      try {
        Assert-Gui
        & $python $seedChecker $sub $item.input_sha256 | Set-Content -LiteralPath (Join-Path $sub 'roundtrip-validation.json') -Encoding UTF8
        $step.exit_code = $LASTEXITCODE
        Assert-Gui
        $step.gui_preserved = $true
        if ($step.exit_code -ne 0) { throw "$seedName roundtrip checker exit=$($step.exit_code)" }
        $step.status = 'completed'
      } catch {
        $step.status = 'failed'; $step.error = $_.Exception.Message
        throw
      } finally {
        $step.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
        ConvertTo-Json -InputObject $steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8
      }
      Write-Output "A08.var04 seed $($item.seed)/32 completed"
    }
  } catch {
    $errorText = $_.Exception.Message
  }
  $sourceAfter = Source-Hashes
  foreach ($key in $sourceBefore.Keys) {
    if ($sourceBefore[$key] -ne $sourceAfter[$key]) { $errorText = "source fingerprint changed during seed matrix: $key" }
  }
  $raw = [ordered]@{}
  foreach ($file in Get-ChildItem -LiteralPath $run -Recurse -File) {
    $relative = $file.FullName.Substring($run.Length+1).Replace('\','/')
    if ($relative -eq 'invocation.json') { continue }
    $raw[$relative] = [ordered]@{ bytes=$file.Length; sha256=(Hash $file.FullName) }
  }
  [ordered]@{ schema='simlox-a08-var04-seed-matrix-v1/closure'; run_id=$RunId; invocation_sha256=(Hash (Join-Path $run 'invocation.json')); source_hashes_before=$sourceBefore; source_hashes_after=$sourceAfter; completed_steps=@($steps|Where-Object status -eq 'completed').Count; expected_steps=160; raw=$raw; error=$errorText; publication_state='not_published' } | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{ run_id=$RunId; run_dir=$run; completed_steps=160; scope='serial_32_seed_native_candidate' } | ConvertTo-Json)
} finally {
  if ($acquired) { $queue.ReleaseMutex() | Out-Null }
  $queue.Dispose()
}

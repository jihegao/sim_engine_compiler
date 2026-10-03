param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9][a-z0-9-]{2,63}$')][string]$RunId,
  [Parameter(Mandatory=$true)][ValidateSet('qty1','qty2')][string]$Arm
)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$root=Split-Path $case -Parent
$inputPath=Join-Path $case "$Arm-input.json"
$parent=Join-Path $root 'G09-var03-default-noncritical-v1.0.1\omitted-nc-b1-input.json'
$parentClosure=Join-Path $root 'G09-var03-default-noncritical-v1.0.1\runs\g09-var03-omitted-nc-b1-v101-ssh-20261003-01\closure.json'
$control=Join-Path $root 'G09-var03-default-noncritical-v1.0.1\omitted-control-input.json'
$controlClosure=Join-Path $root 'G09-var03-default-noncritical-v1.0.1\runs\g09-var03-omitted-control-v101-ssh-20261003-01\closure.json'
$diagnosticQty1=Join-Path $root 'G09-var03-nc-quantity-v1.0.2\qty1-input.json'
$diagnosticQty1Closure=Join-Path $root 'G09-var03-nc-quantity-v1.0.2\runs\g09-var03-qty1-v102-ssh-20261003-01\closure.json'
$diagnosticQty2=Join-Path $root 'G09-var03-nc-quantity-v1.0.2\qty2-input.json'
$diagnosticQty2Closure=Join-Path $root 'G09-var03-nc-quantity-v1.0.2\runs\g09-var03-qty2-v102-ssh-20261003-01\closure.json'
$contract=Join-Path $case 'contract.json'; $diff=Join-Path $case 'exact-diff.json'
$builder=Join-Path $case 'build.py'; $diffBuilder=Join-Path $case 'describe_diff.py'; $checker=Join-Path $case 'check_roundtrip.py'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$manual='C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf'
$dictionary='C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt'
$work='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$run=Join-Path (Join-Path $case 'runs') $RunId
$inputSha=@{'qty1'='9ac974598ee30c5ff06105b97d2984acfc3d96a8e9af6aceb36bb32f60ed914f';'qty2'='79985e3e5987631ad833e387ba50119b41068813e764f9c47e3bcd9f8190bde9'}[$Arm]
$expected=[ordered]@{
  input=$inputSha
  parent='40210448fc3ccabc93c681272bf179026342202ba2ae36cfd8302769523a3e11'
  parent_closure='40cc0d7cdfcc3e2096371fceb7143e29a1d1ba69d494649ba7d1e164ab5cf119'
  control='f3f6c2c45e89627fa5d96f24a0b0ecc9d72f31044234f3f3246d098b6d079fbf'
  control_closure='bb7bbf803c44b8f48d118fdbeb4754f204e88a5f420b837e28f2d75d59c9393f'
  diagnostic_qty1='150160273f2ab14ce9793cae8280d91ae4916449f36fc3195dffd70d32470be9'
  diagnostic_qty1_closure='74f58c19bbaba65080dc14452fab7992e68842a084500360c95333c91884fc85'
  diagnostic_qty2='8fe5537045397b71742df6793c1d9d7b0c5ab73fed03106ce7e78d5c55b636eb'
  diagnostic_qty2_closure='032721073cc4d281011d3b07e7d30e9d8007aa3967340541465c97659c41967d'
  contract='b71c9789685716fbff0c6e2b87b305191a23c4fabe79d7c6ecbcaf397ccddd57'
  exact_diff='393f16ffaf36f629d23bee5643b1ccb45efeb7fc9e196c9296a572bdc53222a1'
  exe='fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0'
  manual='39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3'
  dictionary='11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0'
}
$paths=@{input=$inputPath;parent=$parent;parent_closure=$parentClosure;control=$control;control_closure=$controlClosure;diagnostic_qty1=$diagnosticQty1;diagnostic_qty1_closure=$diagnosticQty1Closure;diagnostic_qty2=$diagnosticQty2;diagnostic_qty2_closure=$diagnosticQty2Closure;contract=$contract;exact_diff=$diff;exe=$exe;manual=$manual;dictionary=$dictionary}
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME) { throw 'session-0 SSH required' }
if (Test-Path -LiteralPath $run) { throw 'immutable run ID already exists' }
$ancestors=@(); $ancestorPid=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
for ($depth=0; $depth -lt 8 -and $ancestorPid -gt 0; $depth++) { $a=Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorPid"; if (-not $a) { break }; $ancestors+=$a.Name; $ancestorPid=$a.ParentProcessId }
if ($ancestors -notcontains 'sshd.exe') { throw 'sshd ancestor absent' }
foreach($key in $expected.Keys) { if (-not (Test-Path -LiteralPath $paths[$key]) -or (Get-FileHash -LiteralPath $paths[$key] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected[$key]) { throw "frozen fingerprint differs: $key" } }
foreach($p in @($contract,$builder,$diffBuilder,$checker,$python,$work)) { if (-not (Test-Path -LiteralPath $p)) { throw "missing source: $p" } }
$frozen=Get-Content -LiteralPath $contract -Raw | ConvertFrom-Json
if ($frozen.case_id -ne 'G09' -or $frozen.variant_id -ne 'G09.var03' -or $frozen.input_sha256.PSObject.Properties[$Arm].Value -ne $inputSha -or $frozen.accepted_parent.input_sha256 -ne $expected.parent -or $frozen.accepted_parent.native_closure_sha256 -ne $expected.parent_closure -or $frozen.accepted_control.input_sha256 -ne $expected.control -or $frozen.accepted_control.native_closure_sha256 -ne $expected.control_closure -or $frozen.excluded_diagnostic.input_sha256.qty1 -ne $expected.diagnostic_qty1 -or $frozen.excluded_diagnostic.native_closure_sha256.qty1 -ne $expected.diagnostic_qty1_closure -or $frozen.excluded_diagnostic.input_sha256.qty2 -ne $expected.diagnostic_qty2 -or $frozen.excluded_diagnostic.native_closure_sha256.qty2 -ne $expected.diagnostic_qty2_closure -or $frozen.exact_diff_sha256 -ne $expected.exact_diff) { throw 'contract pins differ' }
& $python $builder | Out-Null; if ($LASTEXITCODE -ne 0) { throw 'builder verification failed' }
& $python $diffBuilder | Out-Null; if ($LASTEXITCODE -ne 0) { throw 'diff verification failed' }
$queue=[System.Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue'); $held=$false
try {
  try { $held=$queue.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $held=$true }
  if (-not $held) { throw 'native queue busy' }
  $gui=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if ($gui.Count -ne 1 -or $gui[0].Id -ne 13340 -or $gui[0].SessionId -le 0 -or $gui[0].StartTime.ToUniversalTime().ToString('o') -ne '2026-09-28T10:09:56.8261381Z') { throw 'GUI identity differs' }
  $guiStart=$gui[0].StartTime.ToUniversalTime().ToString('o'); $guiSession=$gui[0].SessionId
  $sessions=@(qwinsta 2>&1)
  if ($LASTEXITCODE -ne 0 -or @($sessions | Where-Object { $_ -match ('^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+'+$guiSession+'\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)') }).Count -ne 1) { throw 'GUI session inactive' }
  $optionKey='HKCU:\Software\Systecon\SIMLOX Version 2017\Prelife Settings'
  $optionOriginal=(Get-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog).UsePrelifeLog
  if ($optionOriginal -ne 'NO') { throw "Prelife Log option expected NO, got $optionOriginal" }
  function Assert-Gui { $p=@(Get-Process Simlox -ErrorAction SilentlyContinue); if ($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne $guiSession -or $p[0].StartTime.ToUniversalTime().ToString('o') -ne $guiStart) { throw 'GUI changed' } }
  $sourcePaths=[ordered]@{input=$inputPath;parent=$parent;parent_closure=$parentClosure;control=$control;control_closure=$controlClosure;diagnostic_qty1=$diagnosticQty1;diagnostic_qty1_closure=$diagnosticQty1Closure;diagnostic_qty2=$diagnosticQty2;diagnostic_qty2_closure=$diagnosticQty2Closure;contract=$contract;exact_diff=$diff;builder=$builder;diff_builder=$diffBuilder;checker=$checker;runner=$PSCommandPath;python=$python;exe=$exe;manual=$manual;dictionary=$dictionary}
  function Source-Hashes { $h=[ordered]@{}; foreach($key in $sourcePaths.Keys) { $h[$key]=(Get-FileHash -LiteralPath $sourcePaths[$key] -Algorithm SHA256).Hash.ToLowerInvariant() }; return $h }
  $before=Source-Hashes
  New-Item -ItemType Directory -Path $run -Force | Out-Null
  Copy-Item -LiteralPath $inputPath -Destination (Join-Path $run 'input.json')
  if ((Get-FileHash -LiteralPath (Join-Path $run 'input.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $inputSha) { throw 'copied input differs' }
  $source=Join-Path $run 'input.json'; $sxi=Join-Path $run 'model.sxi'; $sxo=Join-Path $run 'model.sxo'; $round=Join-Path $run 'roundtrip-raw.json'; $report=Join-Path $run 'report-raw.json'
  $commands=@(
    [pscustomobject]@{name='import';args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $source,$sxi,(Join-Path $run 'import.log'))},
    [pscustomobject]@{name='export';args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,$round,(Join-Path $run 'export.log'))},
    [pscustomobject]@{name='calc';args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $run 'run.log'))},
    [pscustomobject]@{name='jsonreport';args=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,$report,(Join-Path $run 'report-export.log'))}
  )
  [ordered]@{schema='simlox-g09-noncritical-quantity-ssh-invocation/v1';case_id='G09';variant_id='G09.var03';arm=$Arm;run_id=$RunId;created_utc=(Get-Date).ToUniversalTime().ToString('o');original_run_dir=$run;source_hashes_before=$before;execution_mode='session0_ssh_cli';session_id=(Get-Process -Id $PID).SessionId;ssh_ancestor_names=$ancestors;gui=[ordered]@{pid=13340;session_id=$guiSession;start_utc=$guiStart};queue_mutex='Global\SimloxIssue18NativeQueue';prelife_log_option_before=$optionOriginal;working_directory=$work;planned_commands=$commands;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'invocation.json') -Encoding UTF8
  $steps=@(); $errorText=$null; $nativeOutcome='not_reached'; $conversion=$null
  foreach($command in $commands) {
    $step=[ordered]@{name=$command.name;arguments=$command.args;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;gui_preserved=$false;status='started';error=$null}; $steps+=$step
    try {
      Assert-Gui
      if ($command.name -eq 'calc') {
        try {
          Set-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog -Value 'YES'
          $process=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $work -WindowStyle Hidden -PassThru -Wait
        } finally { Set-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog -Value $optionOriginal }
      } else { $process=Start-Process -FilePath $exe -ArgumentList $command.args -WorkingDirectory $work -WindowStyle Hidden -PassThru -Wait }
      $step.exit_code=$process.ExitCode
      Assert-Gui; $step.gui_preserved=$true
      if ((Get-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog).UsePrelifeLog -ne $optionOriginal) { throw 'Prelife Log option not restored' }
      if ($step.exit_code -ne 0 -and $command.name -ne 'calc') { throw "$($command.name) exit=$($step.exit_code)" }
      $required=switch($command.name) { 'import' {@('model.sxi','import.log')} 'export' {@('roundtrip-raw.json','export.log')} 'calc' {@('run.log')} 'jsonreport' {@('report-raw.json','report-export.log')} }
      foreach($name in $required) { $p=Join-Path $run $name; if (-not (Test-Path -LiteralPath $p) -or (Get-Item -LiteralPath $p).Length -le 4) { throw "$($command.name) output missing: $name" } }
      if ($command.name -eq 'calc') {
        $log=Get-Content -LiteralPath (Join-Path $run 'run.log') -Raw
        $marker=[regex]::Match($log,'Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)')
        if (-not $marker.Success) { throw 'conversion marker absent' }
        $errorCount=[int]$marker.Groups[1].Value; $warningCount=[int]$marker.Groups[2].Value; $noteCount=[int]$marker.Groups[3].Value
        $conversionText=$log.Substring(0,$marker.Index); $runtimeText=$log.Substring($marker.Index+$marker.Length)
        $warnings=@(); $form=''
        foreach($line in ($conversionText -split "`r?`n")) {
          if ($line -match '^Form: (.+)$') { $form=$Matches[1] }
          if ($line -match '\(warning #(\d+)\)') {
            $code=$Matches[1]
            $classification=if ($code -eq '108' -and $form -eq 'Control') { 'event-log-enabled' }
              elseif ($code -eq '126' -and $form -eq 'System' -and $line -match 'This system contains no items: TEACH-(AIR-01|SUB-A|SUB-B)') { 'system-no-direct-items' }
              else { 'unreviewed' }
            $warnings+=@([ordered]@{form=$form;code=$code;line=$line;classification=$classification})
          }
        }
        $observedCodes=@($warnings | ForEach-Object { $_.code })
        $errors=@([regex]::Matches($conversionText,'\(error #(\d+)\)') | ForEach-Object { $_.Groups[1].Value })
        $conversion=[ordered]@{errors=$errorCount;warnings=$warningCount;notes=$noteCount;error_codes=$errors;warning_codes=$observedCodes;warning_lines=@($warnings | ForEach-Object { $_.line });calc_exit_code=$step.exit_code}
        if ($errorCount -gt 0) {
          if ($errors.Count -ne $errorCount) { throw 'converter error count/code mismatch' }
          $nativeOutcome='converter_error_requires_review'; $step.status='diagnostic_converter_error'; break
        }
        if ($step.exit_code -ne 0) { throw "calc exit=$($step.exit_code) despite zero converter errors" }
        foreach($name in @('model.sxo','model.log')) { $p=Join-Path $run $name; if (-not (Test-Path -LiteralPath $p) -or (Get-Item -LiteralPath $p).Length -le 4) { throw "calc output missing: $name" } }
        $reviewed=($observedCodes -contains '108' -and
          $warnings.Count -eq $warningCount -and $noteCount -eq 0 -and
          @($warnings | Where-Object { $_.classification -eq 'unreviewed' }).Count -eq 0 -and
          -not [regex]::IsMatch($runtimeText,'\(warning #\d+\)|\(error #\d+\)'))
        $nativeOutcome=if ($reviewed) { 'zero_error_reviewed_warnings' } else { 'zero_error_unreviewed_diagnostics' }
      }
      $step.status='completed'
    } catch { $errorText=$_.Exception.Message; $step.status='failed'; $step.error=$errorText; break }
    finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
  }
  if (@($steps | Where-Object { $_.name -eq 'export' -and $_.status -eq 'completed' }).Count -eq 1) {
    $step=[ordered]@{name='check_import_export';started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;exit_code=$null;gui_preserved=$false;status='started';error=$null}; $steps+=$step
    try { Assert-Gui; & $python $checker $run $Arm | Set-Content -LiteralPath (Join-Path $run 'roundtrip-validation.json') -Encoding UTF8; $step.exit_code=$LASTEXITCODE; Assert-Gui; $step.gui_preserved=$true; if ($step.exit_code -ne 0) { throw 'roundtrip check failed' }; $step.status='completed' }
    catch { $step.error=$_.Exception.Message; $errorText=if ($errorText) { "$errorText; roundtrip: $($step.error)" } else { $step.error }; $step.status='failed' }
    finally { $step.completed_utc=(Get-Date).ToUniversalTime().ToString('o'); ConvertTo-Json -InputObject $steps -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'steps.json') -Encoding UTF8 }
  }
  $after=Source-Hashes; foreach($key in $before.Keys) { if ($before[$key] -ne $after[$key]) { $errorText="source changed during run: $key" } }
  if ((Get-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog).UsePrelifeLog -ne $optionOriginal) { $errorText='Prelife Log option not restored' }
  $raw=[ordered]@{}; foreach($file in Get-ChildItem -LiteralPath $run -File) { if ($file.Name -ne 'invocation.json') { $raw[$file.Name]=[ordered]@{bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} } }
  $sxoBytes=if (Test-Path -LiteralPath $sxo) { (Get-Item -LiteralPath $sxo).Length } else { $null }
  [ordered]@{schema='simlox-g09-noncritical-quantity-ssh-closure/v1';arm=$Arm;run_id=$RunId;invocation_sha256=(Get-FileHash -LiteralPath (Join-Path $run 'invocation.json') -Algorithm SHA256).Hash.ToLowerInvariant();source_hashes_before=$before;source_hashes_after=$after;raw=$raw;prelife_log_option_after=(Get-ItemProperty -LiteralPath $optionKey -Name UsePrelifeLog).UsePrelifeLog;native_outcome=$nativeOutcome;conversion=$conversion;sxo_bytes=$sxoBytes;report_present=(Test-Path -LiteralPath $report);error=$errorText;publication_state='not_published'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'closure.json') -Encoding UTF8
  if ($errorText) { throw $errorText }
  Write-Output ([ordered]@{run_id=$RunId;arm=$Arm;run_dir=$run;native_outcome=$nativeOutcome} | ConvertTo-Json)
} finally { if ($held) { $queue.ReleaseMutex() | Out-Null }; $queue.Dispose() }


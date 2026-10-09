param([switch]$PreflightOnly)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$contractPath=Join-Path $case 'contract.json'
$methodManifestPath=Join-Path $case 'method-source-manifest.json'
$prelaunchPath=Join-Path $case 'prelaunch-manifest-v100-run01.json'
$approvalPath=Join-Path $case 'review\independent-prelaunch-go.json'
$staticReviewPath=Join-Path $case 'review\independent-prelaunch-static-go.json'
$methodReviewPath=Join-Path $case 'review\independent-method-review-v100-run01.md'
$exe='C:\Program Files\Systecon\SIMLOX\Simlox.exe'
$python='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$workingDirectory='C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace'
$contract=Get-Content -LiteralPath $contractPath -Raw -Encoding UTF8 | ConvertFrom-Json
$runId=$contract.candidate.run_id
$nativeRunDirectory=$contract.candidate.physical_directory
$queueMutexName='Global\SimloxIssue18NativeQueue'
function Get-Sha([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Assert-CanonicalPath([string]$path){
  if(-not [IO.Path]::IsPathRooted($path) -or [IO.Path]::GetFullPath($path) -cne $path){throw "noncanonical absolute path: $path"}
  $cursor=[IO.Path]::GetPathRoot($path)
  foreach($part in $path.Substring($cursor.Length).Split([IO.Path]::DirectorySeparatorChar)){
    if($part -eq ''){continue};$cursor=Join-Path $cursor $part
    $item=Get-Item -LiteralPath $cursor -Force -ErrorAction SilentlyContinue
    if($item -and (($item.Attributes -band [IO.FileAttributes]::ReparsePoint)-ne 0)){throw "reparse path component: $cursor"}
  }
}
function Get-Ancestry{
  $names=@();$ids=@();$parent=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
  for($depth=0;$depth -lt 10 -and $parent -gt 0;$depth++){
    $item=Get-CimInstance Win32_Process -Filter "ProcessId=$parent";if(-not $item){break}
    $names+=$item.Name;$ids+=[int]$item.ProcessId;$parent=$item.ParentProcessId
  }
  if($names -notcontains 'sshd.exe'){throw 'SSH process ancestry does not contain sshd.exe'}
  return [pscustomobject]@{names=$names;ids=$ids}
}
function Assert-Session0([object]$ancestry){
  if($PSVersionTable.PSVersion.Major -ne 5 -or -not $env:SSH_CONNECTION -or
     (Get-Process -Id $PID).SessionId -ne 0 -or $env:SESSIONNAME){throw 'actual SSH PowerShell 5 session 0 required'}
  if($env:COMPUTERNAME -cne '4700-3' -or $ancestry.names -notcontains 'sshd.exe'){throw 'native host or sshd identity differs'}
}
function Assert-Gui{
  $p=@(Get-Process Simlox -ErrorAction SilentlyContinue)
  if($p.Count -ne 1 -or $p[0].Id -ne 13340 -or $p[0].SessionId -ne 1 -or -not $p[0].Responding -or $p[0].Path -cne $exe -or
     ([DateTimeOffset]$p[0].StartTime.ToUniversalTime()).ToUnixTimeMilliseconds() -ne 1790590196826){throw 'protected SIMLOX GUI PID/session/start/responding identity changed'}
}
function Assert-Wts{
  $rows=@(qwinsta 2>&1);$exit=$LASTEXITCODE
  $active=@($rows|Where-Object{$_ -match '^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+1\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)'})
  if($exit -ne 0 -or $active.Count -ne 1){throw 'WTS active interactive session 1 was not uniquely verified'}
  return ($active[0].Trim())
}
function Assert-NoOtherNative([object]$ancestry){
  $native=@(Get-CimInstance Win32_Process -Filter "Name='Simlox.exe'"|Where-Object{$_.ProcessId -ne 13340})
  if($native.Count -ne 0){throw 'another SIMLOX native process is active'}
  # Contenders must be in session 0; ignore the session-1 PowerShell wrapper that starts SSH.
  $runners=@(Get-CimInstance Win32_Process|Where-Object{$_.SessionId -eq 0 -and
    $_.ProcessId -ne $PID -and $ancestry.ids -notcontains [int]$_.ProcessId -and
    $_.Name -match '^(powershell|pwsh|python|pythonw|cmd)\.exe$' -and
    $_.CommandLine -match '(?i)(run_native_ssh|i05-var09-cmloc-v100|SimloxIssue18NativeQueue)'
  })
  if($runners.Count -ne 0){throw 'another Issue 18 case runner is active'}
}
function Assert-RunPath{
  Assert-CanonicalPath $nativeRunDirectory
  if($nativeRunDirectory -cne $contract.candidate.physical_directory){throw 'contract and runner run directory differ'}
  $exists=Test-Path -LiteralPath $nativeRunDirectory
  if($exists -and -not $script:runCreated){throw 'unique native run directory already exists'}
  if(-not $exists -and $script:runCreated){throw 'owned native run directory disappeared'}
  if($exists -and -not (Test-Path -LiteralPath $nativeRunDirectory -PathType Container)){throw 'owned run path is not a directory'}
  $recoveredRunDirectory=Join-Path (Join-Path $case 'runs') $runId
  if(Test-Path -LiteralPath $recoveredRunDirectory){throw 'unique recovered evidence directory already exists'}
  $fileLine='File: '+(Join-Path $nativeRunDirectory 'model.sxi').Replace('\','/')
  $inputLine='Input file: '+(Join-Path $nativeRunDirectory 'model.sxi')
  $outputLine='Output file: '+(Join-Path $nativeRunDirectory 'model.sxo')
  foreach($line in @($fileLine,$inputLine,$outputLine)){if([Text.Encoding]::ASCII.GetByteCount($line) -gt 199 -or $line -cne [Text.Encoding]::ASCII.GetString([Text.Encoding]::ASCII.GetBytes($line))){throw 'SIMLOX path line is non-ASCII or exceeds 199 bytes'}}
}
function Assert-MethodPins{
  $manifest=Get-Content -LiteralPath $methodManifestPath -Raw -Encoding UTF8|ConvertFrom-Json
  if($manifest.version -cne '1.0.0'){throw 'method-source version differs'}
  foreach($source in $manifest.files){
    $path=Join-Path $case $source.path;Assert-CanonicalPath $path
    if(-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path).Length -ne $source.bytes -or (Get-Sha $path) -cne $source.sha256){throw "method source pin differs: $($source.path)"}
  }
  if((Get-Sha (Join-Path $case 'native-input.json')) -cne $manifest.input_sha256){throw 'child input binding differs'}
  if(-not (Test-Path -LiteralPath $methodReviewPath -PathType Leaf) -or (Get-Content -LiteralPath $methodReviewPath -Raw -Encoding UTF8) -notmatch 'GO_METHOD_ONLY'){throw 'independent method GO absent'}
  return $manifest
}
function Assert-PrelaunchSources([object]$manifest){
  if(-not (Test-Path -LiteralPath $prelaunchPath -PathType Leaf)){throw 'frozen prelaunch manifest absent'}
  if(-not (Test-Path -LiteralPath $staticReviewPath -PathType Leaf)){throw 'independent static GO absent'}
  $static=Get-Content -LiteralPath $staticReviewPath -Raw -Encoding UTF8|ConvertFrom-Json
  if($static.decision -cne 'GO_PRELAUNCH_STATIC' -or $static.manifest_sha256 -cne (Get-Sha $prelaunchPath) -or $static.run_id -cne $runId){throw 'independent static GO does not bind manifest/run'}
  foreach($entry in $manifest.sources){
    Assert-CanonicalPath $entry.path
    if(-not (Test-Path -LiteralPath $entry.path -PathType Leaf) -or (Get-Item -LiteralPath $entry.path).Length -ne $entry.bytes -or (Get-Sha $entry.path) -cne $entry.sha256){throw "prelaunch source pin differs: $($entry.key)"}
  }
  if((Get-Sha $exe) -cne $manifest.simlox_exe_sha256 -or (Get-Sha $python) -cne $manifest.python_sha256){throw 'runtime executable fingerprint differs'}
  if((Get-Sha $methodReviewPath) -cne $manifest.method_review_sha256){throw 'independent method review byte pin differs'}
  if((Get-Sha $PSCommandPath) -cne $manifest.runner_sha256 -or
     (Get-Sha (Join-Path $case 'check_model.py')) -cne $manifest.roundtrip_checker_sha256 -or
     (Get-Sha (Join-Path $case 'author_reader.py')) -cne $manifest.author_reader_sha256){throw 'exact runner or validator source pin differs'}
  if((Get-Sha $manifest.live_catalog.path) -cne $manifest.live_catalog.sha256 -or
     (Get-Item -LiteralPath $manifest.live_catalog.path).Length -ne $manifest.live_catalog.bytes){throw 'live catalog byte pin differs'}
}
function Assert-Guard([object]$ancestry,[object]$manifest){
  Assert-Session0 $ancestry;Assert-Gui;Assert-Wts|Out-Null;Assert-NoOtherNative $ancestry;Assert-RunPath
  if($manifest){Assert-PrelaunchSources $manifest}
}
function Invoke-Captured([string]$name,[string]$program,[string]$arguments,[string]$cwd,[string]$stdout,[string]$stderr){
  foreach($p in @($stdout,$stderr)){if(Test-Path -LiteralPath $p){throw "capture path already exists: $p"}}
  $started=(Get-Date).ToUniversalTime().ToString('o')
  $process=Start-Process -FilePath $program -ArgumentList $arguments -WorkingDirectory $cwd -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  $done=(Get-Date).ToUniversalTime().ToString('o')
  $outFile=Get-Item -LiteralPath $stdout; $errFile=Get-Item -LiteralPath $stderr
  return [ordered]@{name=$name;program=$program;arguments=$arguments;started_utc=$started;completed_utc=$done;
    child_pid=$process.Id;exit_code=$process.ExitCode;stdout_path=$stdout;stdout_bytes=$outFile.Length;stdout_sha256=(Get-Sha $stdout);
    stderr_path=$stderr;stderr_bytes=$errFile.Length;stderr_sha256=(Get-Sha $stderr);status='completed';error=$null}
}
function Assert-ConverterLog([string]$path,[string]$runDirectory){
  if(-not $runDirectory){$runDirectory=$nativeRunDirectory}
  $bytes=[IO.File]::ReadAllBytes($path);$offset=0
  if($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF){$offset=3}
  $text=[Text.Encoding]::UTF8.GetString($bytes,$offset,$bytes.Length-$offset)
  if($text -match '(?<!\r)\n' -or -not $text.EndsWith("`r`n")){throw 'converter log CRLF grammar or terminal newline differs'}
  $lines=$text.Substring(0,$text.Length-2).Split([string[]]@("`r`n"),[StringSplitOptions]::None)
  if($lines.Count -ne 17){throw 'converter physical line count differs'}
  $sxi=Join-Path $runDirectory 'model.sxi';$sxo=Join-Path $runDirectory 'model.sxo'
  $fixed=@{0='Performing simulation';1=('Input file: '+$sxi);2=('Output file: '+$sxo);3='Simulating.';4='Converting input data ...';5=('File: '+$sxi.Replace('\','/'));6='Form: Control';7='rec 1: (warning #108) Enabling simulation log may generate extensive data in log file';8='Form: System';9='rec 1: (warning #126) This system contains no items: TEACH-AIR-01';10='Input conversion completed. Errors: 0, Warnings: 2, Notes: 0';12='Starting simulation...';14='Saving results ...'}
  foreach($i in $fixed.Keys){if($lines[$i] -cne $fixed[$i]){throw "converter fixed line $($i+1) differs"}}
  $labels=@{11='Input data conversion time';13='Simulation time';15='Result saving time';16='Total execution time'}
  foreach($i in $labels.Keys){
    $pattern='^'+[regex]::Escape($labels[$i])+': ([0-9]+(?:\.[0-9]+)?) secs\.$'
    if($lines[$i] -cnotmatch $pattern){throw "converter timing line $($i+1) differs"}
    $n=0.0;if(-not [double]::TryParse($Matches[1],[Globalization.NumberStyles]::Float,[Globalization.CultureInfo]::InvariantCulture,[ref]$n) -or [double]::IsNaN($n) -or [double]::IsInfinity($n) -or $n -lt 0){throw 'nonfinite or negative timing'}
  }
  return [ordered]@{bytes=$bytes.Length;sha256=(Get-Sha $path);physical_lines=17;errors=0;warnings=2;notes=0;warning_codes=@('108','126');path_line=$lines[5];line_endings='CRLF';terminal_crlf=$true}
}
function Save-Json([string]$path,[object]$value){$value|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $path -Encoding UTF8}
function Get-RawMap([string]$path){
  $map=[ordered]@{}
  if(Test-Path -LiteralPath $path -PathType Container){foreach($item in Get-ChildItem -LiteralPath $path -File|Sort-Object Name){$map[$item.Name]=[ordered]@{bytes=$item.Length;sha256=(Get-Sha $item.FullName)}}}
  return $map
}
function Assert-SourceStable([object]$manifest){Assert-PrelaunchSources $manifest}
$ancestry=$null;$mutex=[Threading.Mutex]::new($false,$queueMutexName);$acquired=$false
$preflightPathOut=$null;$script:runCreated=$false;$sourceBefore=$null;$steps=@();$failure=$null
try{
  $ancestry=Get-Ancestry;Assert-Session0 $ancestry
  try{$acquired=$mutex.WaitOne(0)}catch [System.Threading.AbandonedMutexException]{$acquired=$true}
  if(-not $acquired){throw 'host-wide Issue 18 native queue mutex is held'}
  $methodManifest=Assert-MethodPins
  if(-not (Test-Path -LiteralPath $workingDirectory -PathType Container)){throw 'pinned SIMLOX working directory absent'}
  $sessionLine=Assert-Wts;Assert-Gui;Assert-NoOtherNative $ancestry;Assert-RunPath
  $prelaunch=$null
  if(Test-Path -LiteralPath $prelaunchPath -PathType Leaf){$prelaunch=Get-Content -LiteralPath $prelaunchPath -Raw -Encoding UTF8|ConvertFrom-Json}
  if(-not $prelaunch){throw 'prelaunch manifest absent'}
  Assert-PrelaunchSources $prelaunch
  $manifestSha=Get-Sha $prelaunchPath
  $sourceBefore=[ordered]@{};foreach($entry in $prelaunch.sources){$sourceBefore[$entry.key]=$entry.sha256}
  $pureDir=Join-Path $case ('review\preflight-pure-'+(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')+'-'+[guid]::NewGuid().ToString('N').Substring(0,8))
  New-Item -ItemType Directory -Path $pureDir|Out-Null
  $pureChecks=@()
  foreach($tool in @('check_model.py','author_reader.py')){
    Assert-Guard $ancestry $prelaunch
    $args='-X utf8 -B "'+(Join-Path $case $tool)+'" --self-check'
    $name=[IO.Path]::GetFileNameWithoutExtension($tool)
    $capture=Invoke-Captured ('pure-'+$name) $python $args $case (Join-Path $pureDir ($name+'-stdout.bin')) (Join-Path $pureDir ($name+'-stderr.bin'))
    $pureChecks+=$capture
    if($capture.exit_code -ne 0 -or $capture.stderr_bytes -ne 0){throw "pure preflight check failed: $tool"}
  }
  $selfcheck=Get-Content -LiteralPath (Join-Path $pureDir 'author_reader-stdout.bin') -Raw -Encoding UTF8|ConvertFrom-Json
  if($selfcheck.decision -ne 'GO_METHOD_REPLAY' -or $selfcheck.checks_passed -ne $selfcheck.checks_total -or $selfcheck.native_dispatch -ne $false){throw 'method reader self-check result differs'}
  Assert-Guard $ancestry $prelaunch;Assert-SourceStable $prelaunch
  if($PreflightOnly){
    $parentPins=Get-Content -LiteralPath (Join-Path $case 'parent-evidence-pins.json') -Raw -Encoding UTF8|ConvertFrom-Json
    $priorOriginalRunDirectory=$parentPins.accepted_d01_run.original_run_directory
    $priorLog=Join-Path $priorOriginalRunDirectory 'run.log';$priorLogBytes=[IO.File]::ReadAllBytes($priorLog)
    $priorConverterReplay=Assert-ConverterLog $priorLog $priorOriginalRunDirectory
    $bomReplayPath=Join-Path $pureDir 'parent-run-log-with-utf8-bom.bin'
    $bomBytes=New-Object byte[] ($priorLogBytes.Length+3);$bomBytes[0]=0xEF;$bomBytes[1]=0xBB;$bomBytes[2]=0xBF;[Array]::Copy($priorLogBytes,0,$bomBytes,3,$priorLogBytes.Length)
    [IO.File]::WriteAllBytes($bomReplayPath,$bomBytes);$bomReplay=Assert-ConverterLog $bomReplayPath $priorOriginalRunDirectory
    $originalText=[Text.Encoding]::UTF8.GetString($priorLogBytes)
    $mutants=@(
      @('timing','Input data conversion time:','Input data Conversion time:'),
      @('input',('Input file: '+(Join-Path $priorOriginalRunDirectory 'model.sxi')),('Input file: '+(Join-Path $priorOriginalRunDirectory 'model.sxi')+'.wrong')),
      @('output',('Output file: '+(Join-Path $priorOriginalRunDirectory 'model.sxo')),('Output file: '+(Join-Path $priorOriginalRunDirectory 'model.sxo')+'.wrong')),
      @('File',('File: '+(Join-Path $priorOriginalRunDirectory 'model.sxi').Replace('\','/')),('File: '+(Join-Path $priorOriginalRunDirectory 'model.sxi').Replace('\','/')+'.wrong')),
      @('warning','warning #126','warning #999'),@('summary','Errors: 0, Warnings: 2','Errors: 1, Warnings: 2')
    )
    $negativeChecks=@()
    foreach($probe in $mutants){
      $changed=$originalText.Replace($probe[1],$probe[2]);if($changed -ceq $originalText){throw 'converter mutant target absent'}
      $mutantPath=Join-Path $pureDir ('parent-run-log-wrong-'+$probe[0]+'.bin');[IO.File]::WriteAllBytes($mutantPath,[Text.Encoding]::UTF8.GetBytes($changed))
      $rejected=$false;$err=$null;try{Assert-ConverterLog $mutantPath $priorOriginalRunDirectory|Out-Null}catch{$rejected=$true;$err=$_.Exception.Message}
      if(-not $rejected){throw 'converter negative probe passed'}
      $negativeChecks+=@([ordered]@{name=$probe[0];rejected=$true;error=$err;sha256=(Get-Sha $mutantPath)})
    }
    $converterParserSelfCheck=[ordered]@{parent_run_id=$parentPins.accepted_d01_run.run_id;parent_run_log_sha256=(Get-Sha $priorLog);no_bom_exact_log_passed=$true;synthetic_utf8_bom_log_passed=$true;negative_checks=$negativeChecks;native_calls=0;physical_lines=17;warnings=2}
    $preflightPathOut=Join-Path (Join-Path $case 'review') ('preflight-ssh0-'+(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')+'.json')
    if(Test-Path -LiteralPath $preflightPathOut){throw 'fresh preflight receipt path already exists'}
    $receipt=[ordered]@{schema='i05-var09-ssh-preflight/v100';decision='GO_PRELAUNCH_CANDIDATE';run_id=$runId;
      host=$env:COMPUTERNAME;utc=(Get-Date).ToUniversalTime().ToString('o');ps_major=$PSVersionTable.PSVersion.Major;
      ssh_connection=$env:SSH_CONNECTION;ssh_client=$env:SSH_CLIENT;session_name=$env:SESSIONNAME;session_id=0;ssh_ancestors=$ancestry.names;
      wts_active_session_line=$sessionLine;gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true;path=$exe};
      mutex_name=$queueMutexName;mutex_acquired=$acquired;simlox_exe_sha256=(Get-Sha $exe);python_sha256=(Get-Sha $python);
      input_sha256=(Get-Sha (Join-Path $case 'native-input.json'));contract_sha256=(Get-Sha $contractPath);
      method_manifest_sha256=(Get-Sha $methodManifestPath);prelaunch_manifest_sha256=$manifestSha;
      source_hashes=$sourceBefore;run_directory=$nativeRunDirectory;run_directory_absent=$true;
      pure_proof_directory=$pureDir;pure_checks=$pureChecks;selfcheck_summary=$selfcheck;converter_parser_self_check=$converterParserSelfCheck;
      native_process_started=$false;publication_state='not_published'}
    Save-Json (Join-Path $pureDir 'source-hashes.json') $sourceBefore
    $receipt.source_hashes_sha256=Get-Sha (Join-Path $pureDir 'source-hashes.json')
    $receipt.runner_sha256=Get-Sha $PSCommandPath
    Save-Json $preflightPathOut $receipt
    Write-Output $preflightPathOut
    return
  }
  if(-not (Test-Path -LiteralPath $approvalPath -PathType Leaf)){throw 'independent GO_PRELAUNCH approval absent'}
  $approval=Get-Content -LiteralPath $approvalPath -Raw -Encoding UTF8|ConvertFrom-Json
  if($approval.preflight_relative_path -cnotmatch '^review\\preflight-ssh0-\d{8}T\d{9}Z\.json$'){throw 'approval preflight path is outside its frozen review receipt grammar'}
  $preflightPathOut=Join-Path $case $approval.preflight_relative_path;Assert-CanonicalPath $preflightPathOut
  if($approval.schema -ne 'i05-var09-independent-prelaunch-go/v100' -or $approval.decision -ne 'GO_PRELAUNCH' -or
     $approval.run_id -cne $runId -or $approval.native_run_directory -cne $nativeRunDirectory -or
     $approval.manifest_sha256 -cne $manifestSha -or $approval.runner_sha256 -cne (Get-Sha $PSCommandPath) -or
     $approval.contract_sha256 -cne (Get-Sha $contractPath) -or $approval.input_sha256 -cne (Get-Sha (Join-Path $case 'native-input.json')) -or
     $approval.method_manifest_sha256 -cne (Get-Sha $methodManifestPath) -or $approval.method_review_sha256 -cne (Get-Sha $methodReviewPath) -or
     $approval.simlox_exe_sha256 -cne (Get-Sha $exe) -or $approval.python_sha256 -cne (Get-Sha $python) -or
     $approval.preflight_sha256 -cne (Get-Sha $preflightPathOut)){throw 'independent prelaunch approval does not bind current exact sources/run'}
  $preflightReceipt=Get-Content -LiteralPath $preflightPathOut -Raw -Encoding UTF8|ConvertFrom-Json
  if($preflightReceipt.schema -ne 'i05-var09-ssh-preflight/v100' -or $preflightReceipt.decision -ne 'GO_PRELAUNCH_CANDIDATE' -or
     $preflightReceipt.run_id -cne $runId -or $preflightReceipt.prelaunch_manifest_sha256 -cne $manifestSha -or
     $preflightReceipt.runner_sha256 -cne (Get-Sha $PSCommandPath) -or
     $preflightReceipt.native_process_started -ne $false -or $preflightReceipt.run_directory_absent -ne $true){throw 'preflight receipt is not safe for native release'}
  Assert-Guard $ancestry $prelaunch;Assert-SourceStable $prelaunch
  if(Test-Path -LiteralPath $nativeRunDirectory){throw 'native run path appeared after prelaunch'}
  New-Item -ItemType Directory -Path $nativeRunDirectory|Out-Null;$script:runCreated=$true
  $input=Join-Path $case 'native-input.json';$copied=Join-Path $nativeRunDirectory 'input.json'
  Copy-Item -LiteralPath $input -Destination $copied
  if((Get-Sha $copied) -cne $methodManifest.input_sha256){throw 'copied native input hash differs'}
  $sxi=Join-Path $nativeRunDirectory 'model.sxi';$sxo=Join-Path $nativeRunDirectory 'model.sxo'
  $round=Join-Path $nativeRunDirectory 'roundtrip-raw.json';$report=Join-Path $nativeRunDirectory 'report-raw.json'
  $commands=@(
    [pscustomobject]@{name='import';args=('-silent -jimport "{0}" -save "{1}" -log "{2}" -close' -f $copied,$sxi,(Join-Path $nativeRunDirectory 'import.log'))},
    [pscustomobject]@{name='export';args=('"{0}" -silent -jexport "{1}" -log "{2}" -close' -f $sxi,$round,(Join-Path $nativeRunDirectory 'export.log'))},
    [pscustomobject]@{name='calc';args=('"{0}" -silent -threads 1 -calc -log "{1}" -close' -f $sxi,(Join-Path $nativeRunDirectory 'run.log'))},
    [pscustomobject]@{name='jsonreport';args=('"{0}" -silent -jsonreport "{1}" -log "{2}" -close' -f $sxo,$report,(Join-Path $nativeRunDirectory 'report-export.log'))}
  )
  $invocation=[ordered]@{schema='i05-var09-native-invocation/v100';case_id='I05';variant_id='I05.var09';version='1.0.0';run_id=$runId;
    created_utc=(Get-Date).ToUniversalTime().ToString('o');host_name=$env:COMPUTERNAME;original_run_directory=$nativeRunDirectory;
    session=[ordered]@{ps_major=5;session_id=0;session_name=$env:SESSIONNAME;ssh_connection=$env:SSH_CONNECTION;ssh_client=$env:SSH_CLIENT;ssh_ancestors=$ancestry.names};
    gui=[ordered]@{pid=13340;session_id=1;start_unix_ms=1790590196826;responding=$true;wts_active_line=$sessionLine};
    queue_mutex=$queueMutexName;simlox_exe_sha256=(Get-Sha $exe);python_sha256=(Get-Sha $python);
    contract_sha256=(Get-Sha $contractPath);method_manifest_sha256=(Get-Sha $methodManifestPath);prelaunch_manifest_sha256=$manifestSha;
    independent_prelaunch_approval_sha256=(Get-Sha $approvalPath);preflight_sha256=(Get-Sha $preflightPathOut);
    input_sha256=$methodManifest.input_sha256;source_hashes_before=$sourceBefore;
    planned_commands=@($commands|ForEach-Object{[ordered]@{name=$_.name;arguments=$_.args}});scope='four_step_native_candidate';publication_state='not_published'}
  Save-Json (Join-Path $nativeRunDirectory 'invocation.json') $invocation
  $roundtripCheck=$false;$behaviorCheck=$false;$converter=$null;$runError=$null
  foreach($command in $commands){
    Assert-Guard $ancestry $prelaunch;Assert-SourceStable $prelaunch
    $step=[ordered]@{sequence=$steps.Count;name=$command.name;arguments=$command.args;started_utc=(Get-Date).ToUniversalTime().ToString('o');completed_utc=$null;status='started';exit_code=$null;child_pid=$null;stdout_path=$null;stdout_sha256=$null;stdout_bytes=$null;stderr_path=$null;stderr_sha256=$null;stderr_bytes=$null;gui_preserved=$false;error=$null}
    $steps+=$step;Save-Json (Join-Path $nativeRunDirectory 'steps.json') $steps
    try{
      $capture=Invoke-Captured $command.name $exe $command.args $workingDirectory (Join-Path $nativeRunDirectory ($command.name+'-stdout.bin')) (Join-Path $nativeRunDirectory ($command.name+'-stderr.bin'))
      foreach($key in @('exit_code','child_pid','stdout_path','stdout_sha256','stdout_bytes','stderr_path','stderr_sha256','stderr_bytes')){$step[$key]=$capture[$key]}
      if($capture.exit_code -ne 0){throw "$($command.name) exited $($capture.exit_code)"}
      Assert-Gui;Assert-Wts|Out-Null;Assert-NoOtherNative $ancestry;$step.gui_preserved=$true
      $required=switch($command.name){'import'{@('model.sxi','import.log')};'export'{@('roundtrip-raw.json','export.log')};'calc'{@('model.sxo','run.log','model.log')};'jsonreport'{@('report-raw.json','report-export.log')}}
      foreach($file in $required){$p=Join-Path $nativeRunDirectory $file;if(-not (Test-Path -LiteralPath $p -PathType Leaf) -or (Get-Item -LiteralPath $p).Length -le 4){throw "$($command.name) output missing/empty: $file"}}
      if($command.name -eq 'calc'){$converter=Assert-ConverterLog (Join-Path $nativeRunDirectory 'run.log') $nativeRunDirectory}
      $step.status='completed'
    }catch{$step.status='failed';$step.error=$_.Exception.Message;$runError=$step.error;throw}
    finally{$step.completed_utc=(Get-Date).ToUniversalTime().ToString('o');Save-Json (Join-Path $nativeRunDirectory 'steps.json') $steps}
    if($command.name -eq 'export'){
      $stdout=Join-Path $nativeRunDirectory 'roundtrip-check-stdout.bin';$stderr=Join-Path $nativeRunDirectory 'roundtrip-check-stderr.bin'
      $check=Invoke-Captured 'check_import_export' $python ('-X utf8 -B "'+(Join-Path $case 'check_model.py')+'" "'+$nativeRunDirectory+'"') $case $stdout $stderr
      $steps+=@([ordered]@{sequence=$steps.Count;name='check_import_export';arguments=$check.arguments;started_utc=$check.started_utc;completed_utc=$check.completed_utc;status=$(if($check.exit_code -eq 0){'completed'}else{'failed'});exit_code=$check.exit_code;child_pid=$check.child_pid;stdout_path=$stdout;stdout_sha256=$check.stdout_sha256;stdout_bytes=$check.stdout_bytes;stderr_path=$stderr;stderr_sha256=$check.stderr_sha256;stderr_bytes=$check.stderr_bytes;gui_preserved=$true;error=$null})
      Assert-Gui;Assert-Wts|Out-Null;Assert-SourceStable $prelaunch
      $roundResult=Get-Content -LiteralPath $stdout -Raw -Encoding UTF8|ConvertFrom-Json
      if($check.exit_code -ne 0 -or $check.stderr_bytes -ne 0 -or $roundResult.passed -ne $true){throw 'roundtrip import/export identity check failed'}
      $roundtripCheck=$true;Save-Json (Join-Path $nativeRunDirectory 'steps.json') $steps
    }
  }
  $stdout=Join-Path $nativeRunDirectory 'behavior-check-stdout.bin';$stderr=Join-Path $nativeRunDirectory 'behavior-check-stderr.bin'
  $args='-X utf8 -B "'+(Join-Path $case 'author_reader.py')+'" --arm child --model-log "'+(Join-Path $nativeRunDirectory 'model.log')+'" --report "'+$report+'"'
  $check=Invoke-Captured 'check_behavior' $python $args $case $stdout $stderr
  $steps+=@([ordered]@{sequence=$steps.Count;name='check_behavior';arguments=$args;started_utc=$check.started_utc;completed_utc=$check.completed_utc;status=$(if($check.exit_code -eq 0){'completed'}else{'failed'});exit_code=$check.exit_code;child_pid=$check.child_pid;stdout_path=$stdout;stdout_sha256=$check.stdout_sha256;stdout_bytes=$check.stdout_bytes;stderr_path=$stderr;stderr_sha256=$check.stderr_sha256;stderr_bytes=$check.stderr_bytes;gui_preserved=$true;error=$null})
  Assert-Gui;Assert-Wts|Out-Null;Assert-SourceStable $prelaunch
  $behaviorResult=Get-Content -LiteralPath $stdout -Raw -Encoding UTF8|ConvertFrom-Json
  if($check.exit_code -ne 0 -or $check.stderr_bytes -ne 0 -or $behaviorResult.decision -ne 'GO_BOUNDED' -or
     $behaviorResult.log_projection_passed -ne $true -or $behaviorResult.full_typed_report_projection_passed -ne $true -or $behaviorResult.report_cell_count -ne 4044){throw 'native child behavior validation failed'}
  $behaviorCheck=$true;Save-Json (Join-Path $nativeRunDirectory 'steps.json') $steps
  $finalObserved=[ordered]@{};foreach($entry in $prelaunch.sources){$finalObserved[$entry.key]=Get-Sha $entry.path}
  foreach($key in $sourceBefore.Keys){if($sourceBefore[$key] -cne $finalObserved[$key]){throw "source drift after native run: $key"}}
  $finalRaw=Get-RawMap $nativeRunDirectory
  $closure=[ordered]@{schema='i05-var09-native-closure/v100';run_id=$runId;invocation_sha256=(Get-Sha (Join-Path $nativeRunDirectory 'invocation.json'));
    source_hashes_before=$sourceBefore;source_hashes_after=$finalObserved;steps=$steps;converter=$converter;
    roundtrip_check_passed=$roundtripCheck;behavior_check_passed=$behaviorCheck;raw=$finalRaw;error=$null;publication_state='not_published'}
  Save-Json (Join-Path $nativeRunDirectory 'closure.json') $closure
  $recovered=Join-Path $case ('runs\'+$runId);if(Test-Path -LiteralPath $recovered){throw 'recovered evidence directory already exists'}
  New-Item -ItemType Directory -Path $recovered -Force|Out-Null
  foreach($file in Get-ChildItem -LiteralPath $nativeRunDirectory -File){
    $target=Join-Path $recovered $file.Name;Copy-Item -LiteralPath $file.FullName -Destination $target
    if((Get-Sha $file.FullName) -cne (Get-Sha $target)){throw "recovered raw byte copy differs: $($file.Name)"}
    (Get-Item -LiteralPath $target).IsReadOnly=$true
  }
  foreach($file in Get-ChildItem -LiteralPath $nativeRunDirectory -File){(Get-Item -LiteralPath $file.FullName).IsReadOnly=$true}
  $summary=[ordered]@{schema='i05-var09-native-run-summary/v100';run_id=$runId;original_run_directory=$nativeRunDirectory;recovered_run_directory=$recovered;
    closure_sha256=(Get-Sha (Join-Path $nativeRunDirectory 'closure.json'));invocation_sha256=(Get-Sha (Join-Path $nativeRunDirectory 'invocation.json'));
    raw_file_count=$finalRaw.Count;native_steps=@($steps|Where-Object{$_.name -in @('import','export','calc','jsonreport')}|ForEach-Object{[ordered]@{name=$_.name;exit_code=$_.exit_code;started_utc=$_.started_utc;completed_utc=$_.completed_utc}});
    converter_errors=0;roundtrip_check_passed=$roundtripCheck;behavior_check_passed=$behaviorCheck;publication_state='not_published'}
  Save-Json (Join-Path $recovered 'run-summary.json') $summary
}catch{$failure=$_.Exception.Message
  if($PreflightOnly -and -not $preflightPathOut){
    $failurePath=Join-Path (Join-Path $case 'review') ('preflight-failure-'+(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')+'.json')
    $failureReceipt=[ordered]@{schema='i05-var09-preflight-failure/v100';run_id=$runId;host=$env:COMPUTERNAME;error=$failure;utc=(Get-Date).ToUniversalTime().ToString('o');session_id=(Get-Process -Id $PID).SessionId;ssh_connection=$env:SSH_CONNECTION;native_process_started=$false;publication_state='not_published'}
    Save-Json $failurePath $failureReceipt
  }
  if($script:runCreated){
    $observed=[ordered]@{};if($prelaunch -and (Test-Path -LiteralPath $prelaunchPath)){foreach($entry in $prelaunch.sources){$observed[$entry.key]=if(Test-Path -LiteralPath $entry.path){Get-Sha $entry.path}else{$null}}}
    $raw=Get-RawMap $nativeRunDirectory
    $inv=Join-Path $nativeRunDirectory 'invocation.json'
    $seal=[ordered]@{schema='i05-var09-native-failure-seal/v100';run_id=$runId;error=$failure;utc=(Get-Date).ToUniversalTime().ToString('o');
      invocation_sha256=$(if(Test-Path -LiteralPath $inv){Get-Sha $inv}else{$null});source_hashes_before=$sourceBefore;source_hashes_after=$observed;
      steps=$steps;converter=$converter;roundtrip_check_passed=$roundtripCheck;behavior_check_passed=$behaviorCheck;raw=$raw;publication_state='not_published'}
    Save-Json (Join-Path $nativeRunDirectory 'failure-seal.json') $seal
    $closure=[ordered]@{schema='i05-var09-native-closure/v100';run_id=$runId;error=$failure;raw=(Get-RawMap $nativeRunDirectory);publication_state='not_published'}
    Save-Json (Join-Path $nativeRunDirectory 'closure.json') $closure
    $failedRecovered=Join-Path $case ('runs\'+$runId)
    if(-not (Test-Path -LiteralPath $failedRecovered)){
      New-Item -ItemType Directory -Path $failedRecovered|Out-Null
      foreach($file in Get-ChildItem -LiteralPath $nativeRunDirectory -File){
        $target=Join-Path $failedRecovered $file.Name;Copy-Item -LiteralPath $file.FullName -Destination $target
        if((Get-Sha $file.FullName) -cne (Get-Sha $target)){throw 'failed evidence recovery byte mismatch'}
        (Get-Item -LiteralPath $target).IsReadOnly=$true;(Get-Item -LiteralPath $file.FullName).IsReadOnly=$true
      }
    }
  }
  throw
}finally{
  if($acquired){$mutex.ReleaseMutex()|Out-Null};$mutex.Dispose()
}
if($failure){throw $failure}
Write-Output (ConvertTo-Json -InputObject $summary -Depth 10)

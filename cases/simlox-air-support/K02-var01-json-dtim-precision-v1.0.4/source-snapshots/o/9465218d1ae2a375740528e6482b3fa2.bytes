param(
 [ValidateSet('preflight','probe0','probe7','native')][string]$Mode,
 [Parameter(Mandatory=$true)][string]$ExpectedManifestSha,
 [Parameter(Mandatory=$true)][string]$ExpectedReviewSha,
 [Parameter(Mandatory=$true)][string]$GuardianPath,
 [Parameter(Mandatory=$true)][string]$ExpectedGuardianSha
)
$ErrorActionPreference='Stop';$case=$PSScriptRoot;$root=(Resolve-Path (Join-Path $case '..\..\..')).Path
$manifestPath=Join-Path $case 'selected-manifest-v8.json';$script:ancestry=@();$identityRows=New-Object 'Collections.Generic.List[Object]'
function Sha([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
function Save([string]$p,$x){$bytes=[Text.UTF8Encoding]::new($false).GetBytes(($x|ConvertTo-Json -Depth 50));$s=[IO.File]::Open($p,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read);try{$s.Write($bytes,0,$bytes.Length);$s.Flush($true)}finally{$s.Dispose()}}
function Canonical([string]$p){
 if(-not [IO.Path]::IsPathRooted($p) -or [IO.Path]::GetFullPath($p) -cne $p){throw 'noncanonical absolute path'}
 $cursor=[IO.Path]::GetPathRoot($p)
 foreach($part in $p.Substring($cursor.Length).Split('\')){if($part){$cursor=Join-Path $cursor $part;$i=Get-Item -LiteralPath $cursor -Force -ErrorAction SilentlyContinue;if($i -and ($i.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'reparse path'}}}
}
if($ExpectedManifestSha -cnotmatch '^[0-9a-f]{64}$' -or $ExpectedReviewSha -cnotmatch '^[0-9a-f]{64}$' -or $ExpectedGuardianSha -cnotmatch '^[0-9a-f]{64}$' -or (Sha $manifestPath) -cne $ExpectedManifestSha){throw 'external manifest/review/guardian binding differs'}
$m=Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8|ConvertFrom-Json
if($m.schema -cne 'simlox-k02-selected-manifest/v8' -or $m.native_steps.Count -ne 2 -or $m.native_steps[0] -cne 'jimport_save' -or $m.native_steps[1] -cne 'jexport'){throw 'selected manifest scope differs'}
$targetMode=if($Mode -ceq 'preflight'){'native'}else{$Mode};$t=$m.targets.$targetMode
if(-not $t -or $t.mode -cne $targetMode){throw 'target mode differs'}
$decision=if($Mode -ceq 'native'){'GO_PRELAUNCH'}elseif($Mode -ceq 'preflight'){'GO_PRELAUNCH_STATIC'}else{'GO_REAL_BENIGN_EXACT_BOUND'}
$reviewPath=Join-Path $case ('review\independent-'+$Mode+'-go-v8.json')
if((Sha $reviewPath) -cne $ExpectedReviewSha){throw 'external independent receipt differs'}
$review=Get-Content -LiteralPath $reviewPath -Raw -Encoding UTF8|ConvertFrom-Json
if($review.decision -cne $decision -or $review.terminal -ne $true -or $review.manifest_sha256 -cne $ExpectedManifestSha -or $review.run_id -cne $t.run_id -or $review.mode -cne $Mode){throw 'review does not bind selected gate/manifest/mode/run'}
if((Sha $GuardianPath) -cne $ExpectedGuardianSha){throw 'guardian receipt differs'}
$guardian=Get-Content -LiteralPath $GuardianPath -Raw -Encoding UTF8|ConvertFrom-Json
if($guardian.decision -cne 'GO_STANDALONE_SAFETY_ONLY' -or $guardian.terminal -ne $true -or $guardian.manifest_sha256 -cne $ExpectedManifestSha -or $guardian.run_id -cne $t.run_id -or $guardian.native_calls -ne 0 -or @(Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$guardian.guard_pid)").Count -ne 0){throw 'standalone guardian is not terminal or bound'}

function FreshRemoteRefs{
 if($m.git_network.host -cne 'ssh.github.com' -or $m.git_network.port -ne 443 -or $m.git_network.server_alive_interval -ne 5 -or $m.git_network.server_alive_count_max -ne 2 -or $m.git_network.resolver -cne '1.1.1.1' -or $m.git_network.identity_file -cne 'C:\Users\user\.ssh\github_deploy_20260927'){throw 'fixed selected Git profile differs'}
 if((& $m.git.path -C $root remote get-url origin) -cne 'git@github.com:jihegao/sim_engine_compiler.git' -or $LASTEXITCODE -ne 0){throw 'actual repository origin differs'}
 $addresses=@(Resolve-DnsName -Name ssh.github.com -Server 1.1.1.1 -Type A -DnsOnly -QuickTimeout -ErrorAction Stop|Where-Object{$_.Type -eq 'A'}|Select-Object -ExpandProperty IPAddress)
 if($addresses.Count -ne 1 -or $addresses[0] -notmatch '^\d+\.\d+\.\d+\.\d+$' -or [Net.IPAddress]::Parse($addresses[0]).AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork){throw 'unique current IPv4 DNS result required'}
 $wrapper=Join-Path $case 'git_ssh_bounded_v4.py'
 $manifestPath=Join-Path $case 'selected-manifest-v8.json'
 foreach($token in @($m.python.path,$wrapper,$manifestPath,$ExpectedManifestSha,$Mode,$addresses[0])){if(-not $token -or $token -match '[\s"]'){throw 'fixed Git wrapper token unsupported'}}
 $profile=$m.python.path.Replace('\','/')+' -E -X utf8 -B '+$wrapper.Replace('\','/')+' --manifest '+$manifestPath.Replace('\','/')+' --manifest-sha '+$ExpectedManifestSha+' --mode '+$Mode+' --resolved-ip '+$addresses[0]+' --'
 $priorGitSshVariant=$env:GIT_SSH_VARIANT
 try{$env:GIT_SSH_VARIANT='ssh';$refs=@(& $m.git.path -C $root -c ssh.variant=ssh -c ('core.sshCommand='+$profile) ls-remote origin refs/heads/main refs/heads/simlox/main);$code=$LASTEXITCODE}finally{$env:GIT_SSH_VARIANT=$priorGitSshVariant}
 $script:gitFreshnessRows+=@([ordered]@{utc=[DateTime]::UtcNow.ToString('o');exit_code=$code;resolved_ipv4=$addresses[0];resolver='1.1.1.1';host='ssh.github.com';port=443;server_alive_interval=5;server_alive_count_max=2;overall_git_deadline_proven=$false;SSH_network_phase_deadline_seconds=20;SSH_child_terminal_wait_seconds=5;SSH_config_file='/dev/null';Git_network_ssh_sha256=$m.git_network.ssh.sha256;SSH_deadline_scope='After direct Popen owner acquired; not total Git/DNS/creation harddeadline';host_key_alias='github.com';strict_host_key_checking='yes';update_host_keys='no';existing_identity='github_deploy_20260927';refs=$refs;configuration_edits=0})
 if($code -ne 0){throw 'strict selected Git transport failed'}
 return $refs
}
function OneArgRegex([string]$value,[bool]$path){
 if(-not $value -or $value -match '[\s"]'){throw 'selected transport tokens require no whitespace/quotes'}
 $p=[regex]::Escape($value);if($path){$p='(?i:'+$p.Replace('\\','[\\/]')+')'}
 return '(?:"'+$p+'"|'+$p+')'
}
function CurrentTransport{
 $parts=@($env:SSH_CONNECTION -split ' ');if($parts.Count -ne 4 -or $parts[0] -cne '127.0.0.1' -or $parts[2] -cne '127.0.0.1' -or $parts[1] -notmatch '^\d+$' -or $parts[3] -cne '22' -or [int]$parts[1] -lt 1 -or [int]$parts[1] -gt 65535){throw 'exact loopback SSH connection required'}
 $tcp=@(Get-NetTCPConnection -LocalAddress $parts[0] -LocalPort ([int]$parts[1]) -RemoteAddress $parts[2] -RemotePort 22 -State Established -ErrorAction Stop)
 if($tcp.Count -ne 1 -or $tcp[0].OwningProcess -le 0){throw 'current SSH client endpoint owner ambiguous'}
 $client=Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$tcp[0].OwningProcess)"
 if(-not $client -or $client.Name -cne 'ssh.exe' -or $client.SessionId -ne 0 -or -not [String]::Equals($client.ExecutablePath,$m.ssh.path,[StringComparison]::OrdinalIgnoreCase) -or (Sha $client.ExecutablePath) -cne $m.ssh.sha256){throw 'current transport actual SSH executable identity differs'}
 $argv=@($m.ssh.path,'-n','-o','BatchMode=yes','-o','ConnectTimeout=10','-i','C:\Users\user\.ssh\id_rsa','user@127.0.0.1','powershell.exe','-NoProfile','-NonInteractive','-File',((Join-Path $case 'run_selected_ssh_v8.ps1').Replace('\','/')),'-ExpectedManifestSha',$ExpectedManifestSha,'-ExpectedReviewSha',$ExpectedReviewSha,'-Mode',$Mode,'-GuardianPath',$GuardianPath.Replace('\','/'),'-ExpectedGuardianSha',$ExpectedGuardianSha)
 foreach($arg in $argv){if(-not $arg -or $arg -match '[\s"]'){throw 'selected client command token unsupported'}}
 if($client.CommandLine -cne ($argv -join ' ')){throw 'complete current SSH client command differs'}
 $parent=Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$client.ParentProcessId)"
 if(-not $parent -or $parent.SessionId -ne 0 -or -not [String]::Equals($parent.ExecutablePath,$m.python.path,[StringComparison]::OrdinalIgnoreCase) -or (Sha $parent.ExecutablePath) -cne $m.python.sha256){throw 'actual transport Python parent identity differs'}
 $pargs=@($m.python.path,'-E','-X','utf8','-B',(Join-Path $case 'ssh_transport_selected_v8.py'),$Mode,'--review-sha',$ExpectedReviewSha,'--manifest-sha',$ExpectedManifestSha,'--guardian',$GuardianPath.Replace('/','\'),'--guardian-sha',$ExpectedGuardianSha)
 $patterns=@();for($i=0;$i -lt $pargs.Count;$i++){$patterns+=@(OneArgRegex $pargs[$i] ($i -in @(0,5,12)))}
 if($parent.CommandLine -cnotmatch ('^'+($patterns -join ' ')+'$')){throw 'complete selected transport Python command differs'}
 $tuple=[ordered]@{connection=$env:SSH_CONNECTION;client_pid=[int]$client.ProcessId;client_path=$client.ExecutablePath;client_creation_filetime_cim=$client.CreationDate.ToUniversalTime().ToFileTimeUtc();client_command=$client.CommandLine;transport_pid=[int]$parent.ProcessId;transport_path=$parent.ExecutablePath;transport_creation_filetime_cim=$parent.CreationDate.ToUniversalTime().ToFileTimeUtc();transport_command=$parent.CommandLine}
 $text=$tuple|ConvertTo-Json -Depth 8 -Compress;if($script:transportTupleText -and $script:transportTupleText -cne $text){throw 'original current transport identity changed'}
 if(-not $script:transportTupleText){$script:transportTupleText=$text;$script:transportTuple=$tuple}
 return $tuple
}

$script:gitFreshnessRows=@();$script:transportTupleText=$null;$script:transportTuple=$null
function Pins{
 foreach($x in @($m.sources)+@($m.exe,$m.python,$m.git,$m.ssh,$m.powershell,$m.compiler,$m.probe_exe,$m.runner_binary)){Canonical $x.path;if(-not(Test-Path -LiteralPath $x.path -PathType Leaf) -or (Get-Item -LiteralPath $x.path).Length -ne $x.bytes -or (Sha $x.path) -cne $x.sha256){throw "source/tool pin differs: $($x.path)"}}
 foreach($x in @($m.live_index,$m.live_catalog)){if((Sha $x.path) -cne $x.sha256 -or (Get-Item -LiteralPath $x.path).Length -ne $x.bytes){throw 'live index/catalog epoch advanced'}}
 $refs=@(FreshRemoteRefs);if( ($refs -join "`n") -cne ($m.refs.remote -join "`n")){throw 'remote epoch advanced'}
 if((& $m.git.path -C $root rev-parse HEAD) -cne $m.refs.HEAD){throw 'worktree HEAD changed'}
}
function Settings{
 $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;if($sid -cne $m.settings.user_sid){throw 'SSH user SID differs'}
 $k=Get-Item -LiteralPath 'HKCU:/Software/Systecon/SIMLOX Version 2017/JSON Import/Export';if(@($k.GetValueNames()).Count -ne $m.settings.values.Count){throw 'JSON settings keyset differs'}
 foreach($v in $m.settings.values){if($k.GetValueNames() -cnotcontains $v.name -or $k.GetValueKind($v.name).ToString() -cne $v.kind -or $k.GetValue($v.name) -cne $v.value){throw 'JSON export settings differ'}}
 return [ordered]@{user_sid=$sid;values=$m.settings.values;observed_utc=[DateTime]::UtcNow.ToString('o');read_only=$true}
}
function Safety([uint32]$childPid,[UInt64]$made,[uint32]$childSession){
 $script:ancestry=@();$cursor=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
 for($i=0;$i -lt 15 -and $cursor -gt 0;$i++){$a=Get-CimInstance Win32_Process -Filter "ProcessId=$cursor";if(-not $a){break};$script:ancestry+=@([ordered]@{pid=[int]$a.ProcessId;name=$a.Name;session=[int]$a.SessionId;created=$a.CreationDate});$cursor=$a.ParentProcessId}
 if($env:COMPUTERNAME -cne '4700-3' -or $PSVersionTable.PSVersion.Major -ne 5 -or (Get-Process -Id $PID).SessionId -ne 0 -or -not $env:SSH_CONNECTION -or $env:SESSIONNAME -or @($script:ancestry|Where-Object{$_.name -ceq 'sshd.exe'}).Count -eq 0){throw 'actual SSH0 PS5 ancestry required'}
 $g=@(Get-Process Simlox -ErrorAction SilentlyContinue);$others=@($g|Where-Object{$_.Id -ne $m.gui.pid})
 if($g.Count -ne $(if($childPid -and $targetMode -ceq 'native'){2}else{1}) -or $others.Count -ne $(if($childPid -and $targetMode -ceq 'native'){1}else{0})){throw 'unexpected native/GUI process set'}
 $gui=@($g|Where-Object{$_.Id -eq $m.gui.pid});if($gui.Count -ne 1 -or $gui[0].SessionId -ne $m.gui.session -or $gui[0].Path -cne $m.exe.path -or -not $gui[0].Responding -or ([DateTimeOffset]$gui[0].StartTime.ToUniversalTime()).ToUnixTimeMilliseconds() -ne $m.gui.start_unix_ms){throw 'protected GUI identity differs'}
 if($others.Count -and ($others[0].Id -ne $childPid -or $others[0].SessionId -ne 0 -or $others[0].Path -cne $m.exe.path -or $others[0].StartTime.ToUniversalTime().ToFileTimeUtc() -ne [long]$made)){throw 'owned suspended native identity differs'}
 $wts=@(qwinsta 2>&1);if($LASTEXITCODE -ne 0 -or @($wts|Where-Object{$_ -match '^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+1\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)'}).Count -ne 1){throw 'active WTS1 not unique'}
 $transport=CurrentTransport
 $exclude=@($PID)+@($script:ancestry|ForEach-Object{$_.pid})+@($transport.client_pid,$transport.transport_pid);if($childPid){$exclude+=@([int]$childPid)}
 $other=@(Get-CimInstance Win32_Process|Where-Object{$_.SessionId -eq 0 -and $_.ProcessId -notin $exclude -and $_.Name -match '^(powershell|pwsh|python|pythonw|cmd|ssh)\.exe$' -and $_.CommandLine -match '(?i)(run_native_ssh|run_selected_ssh|SimloxIssue18NativeQueue|k02-json-dtim-v10[1-4])'})
 if($other.Count){throw 'another native runner contender'}
 Canonical $t.physical_directory;Canonical $t.recovered_directory
 if(Test-Path -LiteralPath $t.recovered_directory){throw 'recovered target occupied before terminal seal'}
 foreach($line in @(('Importing data from Json file: '+(Join-Path $t.physical_directory 'input.json')),('Exporting data to Json file: '+(Join-Path $t.physical_directory 'roundtrip-raw.json')))){if($line -cne [Text.Encoding]::ASCII.GetString([Text.Encoding]::ASCII.GetBytes($line)) -or [Text.Encoding]::ASCII.GetByteCount($line) -gt 199){throw 'unsafe native path length/encoding'}}
 Pins;Settings|Out-Null
}
function Identity([uint32]$childPid,[UInt64]$made,[uint32]$childSession){
 $live=Get-CimInstance Win32_Process -Filter "ProcessId=$childPid";$p=Get-Process -Id $childPid -ErrorAction Stop
 $expected=if($targetMode -ceq 'native'){$m.exe.path}else{$m.probe_exe.path}
 $handleStart=[DateTime]::FromFileTimeUtc([long]$made);$handleMs=([DateTimeOffset]$handleStart).ToUnixTimeMilliseconds();$cimMs=([DateTimeOffset]$live.CreationDate.ToUniversalTime()).ToUnixTimeMilliseconds()
 if(-not $live -or $live.SessionId -ne 0 -or $childSession -ne 0 -or $live.ParentProcessId -ne $PID -or $live.ExecutablePath -cne $expected -or $p.Path -cne $expected -or $p.SessionId -ne 0 -or $p.StartTime.ToUniversalTime().ToFileTimeUtc() -ne [long]$made -or $cimMs -ne $handleMs){throw 'independent suspended child PID/creation/session/parent/path differs'}

 $markerWitness=$null
 if($targetMode -cne 'native'){
  $markerPath=Join-Path $t.physical_directory 'child.marker';$present=Test-Path -LiteralPath $markerPath -ErrorAction Stop
  $markerWitness=[ordered]@{schema='issue18-selected-benign-marker-before-resume/v1';utc=[DateTime]::UtcNow.ToString('o');mode=$Mode;run_id=$t.run_id;manifest_sha256=$ExpectedManifestSha;child_pid=$childPid;child_creation_filetime=$made;marker_path=$markerPath;test_path_present=[bool]$present;marker_absent=(-not $present);phase='actual identity callback after CreateProcessW returned, before this owner ResumeThread';OS_suspended_count_proof='not inferred from Test-Path; actual same-thread Resume result recorded separately'}
  Save (Join-Path $case ('review\marker-before-resume-'+$t.run_id+'.json')) $markerWitness
  if($present){throw 'benign child marker present before owner Resume; no resume permission'}
 }

 $identityRows.Add([ordered]@{marker_witness=$markerWitness;pid=[int]$childPid;creation_filetime=$made;session=0;parent_pid=$PID;path=$live.ExecutablePath;cim_creation=$live.CreationDate;process_creation=$p.StartTime.ToUniversalTime();observed_before_resume=$true;ssh_ancestors=$script:ancestry})
}
function BoundPin($x){if((Sha $x.path) -cne $x.sha256 -or (Get-Item -LiteralPath $x.path).Length -ne $x.bytes){throw 'required preceding receipt differs'};Get-Content -LiteralPath $x.path -Raw -Encoding UTF8|ConvertFrom-Json}
function BenignAccepted{
 $b=BoundPin $review.benign_acceptance
 if($b.decision -cne 'GO_SELECTED_REAL_BENIGN_ACCEPTED' -or $b.terminal -ne $true -or $b.manifest_sha256 -cne $ExpectedManifestSha -or $b.probe0_run_id -cne $m.targets.probe0.run_id -or $b.probe7_run_id -cne $m.targets.probe7.run_id){throw 'separately terminal real benign acceptance required'}
}
Safety 0 0 0
if((Test-Path -LiteralPath $t.physical_directory) -or (Test-Path -LiteralPath $t.recovered_directory)){throw 'one-shot target occupied'}
if($Mode -ceq 'preflight' -or $Mode -ceq 'native'){BenignAccepted}
if($Mode -ceq 'native'){
 $pf=BoundPin $review.preflight
 if($pf.decision -cne 'GO_PRELAUNCH_CANDIDATE' -or $pf.manifest_sha256 -cne $ExpectedManifestSha -or $pf.run_id -cne $t.run_id -or $pf.native_process_started -ne $false -or $pf.run_directory_absent -ne $true -or $pf.ps_major -ne 5 -or $pf.session_id -ne 0){throw 'actual pure preflight differs'}
 $tr=BoundPin $review.preflight_transport
 if($tr.mode -cne 'preflight' -or $tr.exit_code -ne 0 -or $tr.error -or $tr.source_stability_error -or $tr.manifest_sha256 -cne $ExpectedManifestSha -or $tr.run_id -cne $t.run_id){throw 'plain preflight transport receipt differs'}
}elseif($Mode -cne 'preflight'){
 $permit=BoundPin $review.separate_benign_permission
 if($permit.decision -cne 'ALLOW_REAL_BENIGN_EXACT_BOUND' -or $permit.manifest_sha256 -cne $ExpectedManifestSha -or $permit.run_id -cne $t.run_id -or $permit.mode -cne $Mode){throw 'separate exact-bound benign permission required'}
}
$stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ');$receipt=Join-Path $case ('review\'+$Mode+'-'+$stamp+'.json')
if($Mode -ceq 'preflight'){
 $mu=[Threading.Mutex]::new($false,'Global\SimloxIssue18NativeQueue');$owned=$false
 try{try{$owned=$mu.WaitOne(0)}catch [Threading.AbandonedMutexException]{Save $receipt ([ordered]@{decision='NO_GO_ABANDONED_QUEUE';manifest_sha256=$ExpectedManifestSha;run_id=$t.run_id;native_process_started=$false});while($true){Start-Sleep -Seconds 1}};if(-not $owned){throw 'NativeQueue held'};Safety 0 0 0
  Save $receipt ([ordered]@{schema='simlox-k02-selected-preflight/v8';transport_identity=$script:transportTuple;git_freshness=$script:gitFreshnessRows;decision='GO_PRELAUNCH_CANDIDATE';utc=[DateTime]::UtcNow.ToString('o');run_id=$t.run_id;manifest_sha256=$ExpectedManifestSha;static_review_sha256=$ExpectedReviewSha;guardian_sha256=$ExpectedGuardianSha;runner_sha256=(Sha $PSCommandPath);host=$env:COMPUTERNAME;ps_major=5;session_id=0;ssh_connection=$env:SSH_CONNECTION;ssh_ancestors=$script:ancestry;settings=(Settings);gui=$m.gui;native_queue_held=$true;native_queue_abandoned=$false;run_directory_absent=$true;native_process_started=$false})
 }finally{if($owned){$mu.ReleaseMutex()};$mu.Dispose()};Write-Output $receipt;exit 0
}
Add-Type -Path $m.runner_binary.path
[Issue18SelectedK02V3.SelectedOwner]::CheckAbi()
$cfg=New-Object Issue18SelectedK02V3.Config;$cfg.Mode=$targetMode;$cfg.RunId=$t.run_id;$cfg.Physical=$t.physical_directory;$cfg.Recovered=$t.recovered_directory;$cfg.Review=Join-Path $case 'review';$cfg.WorkingDirectory=$m.working_directory;$cfg.InputSource=Join-Path $case 'native-input.json';$cfg.InputSha=$m.input_sha256;$cfg.ExecutableSha=if($targetMode -ceq 'native'){$m.exe.sha256}else{$m.probe_exe.sha256}
$fresh=[Action[uint32,UInt64,uint32]]{param($p,$made,$s) Safety $p $made $s}
$independent=[Action[uint32,UInt64,uint32]]{param($p,$made,$s) Identity $p $made $s}
$validate=[Action[string]]{param($raw)
 $out=@(& $m.python.path -E -X utf8 -B (Join-Path $case 'check_exchange_v2.py') --binding-sha $m.component_binding_sha256 --raw-directory $raw --input-path (Join-Path $raw 'input.json') --output-path (Join-Path $raw 'roundtrip-raw.json'))
 $code=$LASTEXITCODE;Save (Join-Path $case ('review\raw-check-'+$t.run_id+'.json')) ([ordered]@{checker_exit_code=$code;stdout_text_lines=$out;capture_kind='PowerShell decoded text, not original model raw bytes';manifest_sha256=$ExpectedManifestSha;run_id=$t.run_id})
 if($code -ne 0){throw 'readonly raw checker failed'};$x=($out -join "`n")|ConvertFrom-Json
 if($x.status -cne 'RAW_IDENTITY_CHECK_ONLY' -or $x.cells -ne 381 -or $x.actual_target_independently_verified -ne $true -or $x.publication_GO -ne $false){throw 'full typed raw/binary64/log acceptance differs'}
}
# This synchronous call owns all original process/file handles and NativeQueue.
# There is deliberately no PowerShell finally release/kill/retry around it.
$result=[Issue18SelectedK02V3.SelectedOwner]::Execute($cfg,$fresh,$independent,$validate)
Save $receipt ([ordered]@{schema='simlox-k02-selected-owning-result/v8';execution_adapter_version=8;transport_identity=$script:transportTuple;git_freshness=$script:gitFreshnessRows;mode=$Mode;run_id=$t.run_id;manifest_sha256=$ExpectedManifestSha;independent_gate_sha256=$ExpectedReviewSha;guardian_sha256=$ExpectedGuardianSha;result=$result;independent_suspended_identity=$identityRows;publication_state='not_published';denominator=$null})
Write-Output $receipt
if($Mode -ceq 'probe7'){if(-not $result.Failed -or $result.Children.Count -ne 1 -or -not $result.Children[0].ExitCodeObserved -or $result.Children[0].ExitCode -ne 7 -or -not $result.RecoveryVerified -or -not $result.QueueReleasedActual){exit 1};exit 0}
if($result.Failed -or -not $result.QueueReleasedActual -or ($Mode -ceq 'native' -and -not $result.RawBehaviorAccepted)){exit 1};exit 0

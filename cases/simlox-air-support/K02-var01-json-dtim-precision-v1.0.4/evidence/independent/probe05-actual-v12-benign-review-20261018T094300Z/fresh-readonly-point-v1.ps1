$ErrorActionPreference='Stop'
$output='C:\Users\user\Documents\Codex\2026-10-10\issue18-cli-20261009T195400Z\probe05-actual-v12-benign-review-20261018T094300Z\fresh-readonly-point-v1.json'
$started=[DateTime]::UtcNow.ToString('o')
$snapshot=@(Get-CimInstance Win32_Process)
$reviewPid=$PID
$exclude=@([int]$reviewPid)
$ancestors=@()
$cursor=($snapshot|Where-Object{$_.ProcessId -eq $reviewPid}).ParentProcessId
for($step=0;$step -lt 20 -and $cursor -gt 0;$step++){
 $item=@($snapshot|Where-Object{$_.ProcessId -eq $cursor})
 if($item.Count -ne 1){break}
 $entry=$item[0];$exclude+=[int]$entry.ProcessId
 $ancestors+=@([ordered]@{pid=[int]$entry.ProcessId;parent=[int]$entry.ParentProcessId;name=$entry.Name;session=[int]$entry.SessionId;created_utc=$entry.CreationDate.ToUniversalTime().ToString('o')})
 $cursor=$entry.ParentProcessId
}
$originalOwner=@($snapshot|Where-Object{$_.ProcessId -eq 79044})
$originalParent=@($snapshot|Where-Object{$_.ProcessId -eq 62444})
$directChildren=@($snapshot|Where-Object{$_.ParentProcessId -eq 79044})
$contenders=@($snapshot|Where-Object{$_.SessionId -eq 0 -and $_.ProcessId -notin $exclude -and $_.Name -match '^(powershell|pwsh|python|pythonw|cmd|ssh)\.exe$' -and $_.CommandLine -match '(?i)(run_native_ssh|run_selected_ssh|SimloxIssue18NativeQueue|k02-json-dtim-v10[1-4])'}|ForEach-Object{[ordered]@{pid=[int]$_.ProcessId;parent=[int]$_.ParentProcessId;name=$_.Name;path=$_.ExecutablePath;created_utc=$_.CreationDate.ToUniversalTime().ToString('o');command=$_.CommandLine}})
$simlox=@($snapshot|Where-Object{$_.Name -ieq 'Simlox.exe'}|ForEach-Object{[ordered]@{pid=[int]$_.ProcessId;parent=[int]$_.ParentProcessId;session=[int]$_.SessionId;path=$_.ExecutablePath;created_utc=$_.CreationDate.ToUniversalTime().ToString('o')}})
$gui=Get-Process -Id 13340 -ErrorAction Stop
$guiPoint=[ordered]@{pid=$gui.Id;session=$gui.SessionId;creation_filetime_decimal=$gui.StartTime.ToUniversalTime().ToFileTimeUtc().ToString([Globalization.CultureInfo]::InvariantCulture);path=$gui.Path;responding=$gui.Responding}
$wts=@(& 'C:\Windows\System32\qwinsta.exe' 2>&1)
$wtsExit=$LASTEXITCODE
$active=@($wts|Where-Object{$_ -match '^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+1\s+(?:Active|\u8fd0\u884c\u4e2d)(?:\s|$)'})
$point=[ordered]@{started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o');host=$env:COMPUTERNAME;review_pid=$reviewPid;review_session=(Get-Process -Id $reviewPid).SessionId;PS_version=$PSVersionTable.PSVersion.ToString();excluded_only_current_reader_and_its_ancestors=$exclude;ancestors=$ancestors;original_owner_pid_present=($originalOwner.Count -ne 0);original_parent_pid_present=($originalParent.Count -ne 0);remaining_direct_children_count=$directChildren.Count;native_contenders=$contenders;simlox_processes=$simlox;gui=$guiPoint;wts_exit=$wtsExit;wts=$wts;active_session1_rows=$active.Count;process_mutations=0;queue_operations=0;CLIExecutor_operations=0;native_calls=0;SSH_calls=0;scope='Point-in-time read-only process snapshot; preCreate immutable source and retained-H terminal evidence supply original-child noncreation,not absence alone.'}
$encoded=[Text.UTF8Encoding]::new($false).GetBytes(($point|ConvertTo-Json -Depth 15))
$stream=[IO.File]::Open($output,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
try{$stream.Write($encoded,0,$encoded.Length);$stream.Flush($true)}finally{$stream.Dispose()}
if($originalOwner.Count -ne 0 -or $originalParent.Count -ne 0 -or $directChildren.Count -ne 0 -or $contenders.Count -ne 0){throw 'Original owner/parent/child/contender present'}
if($guiPoint.creation_filetime_decimal -cne '134350637968261381' -or $guiPoint.session -ne 1 -or $guiPoint.path -ine 'C:\Program Files\Systecon\SIMLOX\Simlox.exe' -or -not $guiPoint.responding -or $wtsExit -ne 0 -or $active.Count -ne 1){throw 'Protected GUI/WTS point differs'}
Write-Output ($point|ConvertTo-Json -Depth 15)

$ErrorActionPreference='Stop'
$repo='C:/Users/user/Documents/Codex/2026-09-29/simlox-c04-deadline/repo'
$casePath=$repo+'/cases/simlox-air-support/C02-var01-personnel-zero-v1.0.1'
$helper=$casePath+'/captured_process.ps1'
if((Get-FileHash -LiteralPath $helper).Hash.ToLower() -ne '62884c118c0bba7b10a20f9b4a124d524f499a1be9d85cd270c1c1d11951cf5a'){throw 'Capture helper changed'}
. $helper
$approvalPath=$casePath+'/review/independent-prelaunch-go.json'
if((Get-FileHash -LiteralPath $approvalPath).Hash.ToLower() -ne '84fe2b79dba385513ba4781050b452087480065e0f63bcc335291a1f52686e35'){throw 'Independent approval changed'}
if((Get-FileHash -LiteralPath ($casePath+'/prelaunch-manifest.json')).Hash.ToLower() -ne 'c1c2665b9e8c8a7e054c47395a91110e0f4852605573ca49bc6aa69b2308e6e2'){throw 'Manifest changed'}
if((Get-FileHash -LiteralPath ($casePath+'/run_native_ssh.ps1')).Hash.ToLower() -ne '175656baa5cadd49a9b9db85862bcfa5c933c205a8514c4c8f996c164f300d94'){throw 'Runner changed'}
$stdout=$repo+'/tmp/c02-var01-v101-native-driver-20261007.stdout.txt'
$stderr=$repo+'/tmp/c02-var01-v101-native-driver-20261007.stderr.txt'
$receiptPath=$repo+'/tmp/c02-var01-v101-native-driver-20261007.json'
if(Test-Path -LiteralPath $receiptPath){throw 'Driver receipt exists'}
$client=(Get-Command ssh.exe -ErrorAction Stop).Source
$arguments='-n -o BatchMode=yes -o ConnectTimeout=10 -i C:/Users/user/.ssh/id_rsa user@127.0.0.1 powershell.exe -NoProfile -NonInteractive -File '+$casePath+'/run_native_ssh.ps1'
$record=Invoke-CapturedProcess $client $arguments $repo $stdout $stderr (Get-Process -Id $PID).SessionId
$receipt=[ordered]@{schema='issue18-c02-var01-v101-root-ssh-native-driver/v1';utc=[DateTime]::UtcNow.ToString('o');purpose='actual SSH PowerShell5 sole native child under GO_PRELAUNCH';capture=$record;stdout_sha256=(Get-FileHash -LiteralPath $stdout).Hash.ToLower();stderr_sha256=(Get-FileHash -LiteralPath $stderr).Hash.ToLower()}
[IO.File]::WriteAllText($receiptPath,($receipt|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
foreach($path in @($stdout,$stderr,$receiptPath)){(Get-Item -LiteralPath $path).IsReadOnly=$true}
$receipt|ConvertTo-Json -Depth 6
Get-Content -LiteralPath $stdout -Raw
if((Get-Item -LiteralPath $stderr).Length -gt 0){Get-Content -LiteralPath $stderr -Raw}
Assert-SuccessfulCapture $record (Get-Process -Id $PID).SessionId | Out-Null
param(
 [Parameter(Mandatory=$true)][string]$RunId,
 [Parameter(Mandatory=$true)][string]$InputSha256
)
$ErrorActionPreference='Stop'
Write-Output "B03 loopback wrapper: session=$((Get-Process -Id $PID).SessionId); SSH=$([bool]$env:SSH_CONNECTION)"
& (Join-Path $PSScriptRoot 'run_native_ssh.ps1') -RunId $RunId -InputSha256 $InputSha256 -AllowExistingGui
if(-not $?) { throw 'B03 native runner failed' }

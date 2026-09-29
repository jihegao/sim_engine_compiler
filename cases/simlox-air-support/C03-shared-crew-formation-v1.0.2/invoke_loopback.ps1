param(
 [Parameter(Mandatory=$true)][string]$RunId,
 [Parameter(Mandatory=$true)][string]$VariantId,
 [Parameter(Mandatory=$true)][string]$InputSha256
)
$ErrorActionPreference='Stop'
Write-Output "C03 loopback wrapper: session=$((Get-Process -Id $PID).SessionId); SSH=$([bool]$env:SSH_CONNECTION)"
& (Join-Path $PSScriptRoot 'run_native_ssh.ps1') -RunId $RunId -VariantId $VariantId -InputSha256 $InputSha256 -AllowExistingGui
if(-not $?) { throw 'C03 native runner failed' }

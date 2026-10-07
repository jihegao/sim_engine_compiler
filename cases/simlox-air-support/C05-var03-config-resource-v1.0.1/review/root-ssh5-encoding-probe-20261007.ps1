$ErrorActionPreference = 'Stop'
if (-not $env:SSH_CONNECTION -or (Get-Process -Id $PID).SessionId -ne 0 -or $PSVersionTable.PSVersion.Major -ne 5) { throw 'actual SSH PowerShell5 session0 required' }
$source = 'C:/Users/user/Documents/Codex/2026-09-29/simlox-c04-deadline/repo/cases/simlox-air-support/C05-var03-config-resource-v1.0.1/contract.json'
$before = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
if ($before -ne 'cc3aa75b3c4f6cec8fff57c0de28abf9ed552f4c0bc836e581295856ca30f283') { throw 'frozen source drift' }
$defaultOk = $false
$defaultErrorType = $null
try { $discard = Get-Content -LiteralPath $source -Raw | ConvertFrom-Json; $defaultOk = $true } catch { $defaultErrorType = $_.Exception.GetType().FullName }
$utf8 = Get-Content -LiteralPath $source -Raw -Encoding UTF8 | ConvertFrom-Json
$after = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
if ($before -ne $after -or $utf8.version -ne '1.0.1') { throw 'UTF8 verification/source identity failed' }
$result = [ordered]@{schema='c05-var03-ssh5-encoding-probe/v1';utc=(Get-Date).ToUniversalTime().ToString('o');powershell_version=$PSVersionTable.PSVersion.ToString();self_session=0;ssh_present=$true;source_sha256_before=$before;source_sha256_after=$after;default_decode_json_passed=$defaultOk;default_decode_error_type=$defaultErrorType;explicit_utf8_json_passed=$true;parsed_version=$utf8.version;native_process_started=$false}
$result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath 'C:/Users/user/Documents/Codex/2026-09-29/simlox-c04-deadline/repo/cases/simlox-air-support/C05-var03-config-resource-v1.0.1/review/root-ssh5-encoding-probe-20261007.json' -Encoding UTF8
$result | ConvertTo-Json -Depth 4

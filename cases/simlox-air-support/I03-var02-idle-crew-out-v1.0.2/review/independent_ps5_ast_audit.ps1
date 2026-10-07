$ErrorActionPreference = 'Stop'
$casePath = Split-Path -Parent $PSScriptRoot
if ($PSVersionTable.PSVersion.Major -ne 5) { throw 'Windows PowerShell 5 required' }
$names = @('run_native_ssh_v3.ps1', 'captured_process.ps1', 'preflight_receipt.ps1',
           'checker_receipt.ps1', 'test_preflight_receipt.ps1', 'test_checker_receipt.ps1')
foreach ($name in $names) {
  $tokens = $null
  $errors = $null
  [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $casePath $name),
    [ref]$tokens, [ref]$errors) | Out-Null
  if ($errors.Count -ne 0) { throw "$name AST errors: $($errors.Count)" }
}
Write-Output "PS5_AST_PASS files=$($names.Count) errors=0"

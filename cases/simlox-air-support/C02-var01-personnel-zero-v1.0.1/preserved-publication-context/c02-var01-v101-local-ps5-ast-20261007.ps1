$ErrorActionPreference='Stop'
if($PSVersionTable.PSVersion.Major -ne 5){throw 'Actual PS5 required'}
$casePath='C:/Users/user/Documents/Codex/2026-09-29/simlox-c04-deadline/repo/cases/simlox-air-support/C02-var01-personnel-zero-v1.0.1'
$records=@()
foreach($name in @('run_native_ssh.ps1','captured_process.ps1','preflight_receipt.ps1','checker_receipt.ps1','test_preflight_receipt.ps1','test_checker_receipt.ps1')){
 $tokens=$null;$errors=$null;$path=Join-Path $casePath $name
 $ast=[Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors)
 if(@($errors).Count -gt 0){throw ($errors|Out-String)}
 $records += [ordered]@{name=$name;sha256=(Get-FileHash -LiteralPath $path).Hash.ToLower();parser_errors=0}
}
[ordered]@{schema='issue18-c02-var01-v101-local-ps5-ast/v1';ps_major=$PSVersionTable.PSVersion.Major;files=$records;native_started=$false}|ConvertTo-Json -Depth 5
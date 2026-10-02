param([switch]$VerifyExisting)
$ErrorActionPreference='Stop'
$case=(Resolve-Path $PSScriptRoot).Path
$runner=Join-Path $case 'run_native_ssh.ps1'
$key='C:\Users\user\.ssh\id_rsa'
foreach($seed in 2..13) {
  foreach($arm in @('baseline','qty-two','env-two')) {
    $id=('g12-var02-seed{0:D2}-{1}-20261003-01' -f $seed,$arm)
    $run=Join-Path (Join-Path $case 'runs') $id
    if (Test-Path -LiteralPath $run) {
      if (-not $VerifyExisting) { throw "existing run requires explicit verification: $id" }
      $closurePath=Join-Path $run 'closure.json'
      if (-not (Test-Path -LiteralPath $closurePath)) { throw "closure missing: $id" }
      $closure=Get-Content -LiteralPath $closurePath -Raw | ConvertFrom-Json
      if ($closure.run_id -ne $id -or $closure.seed -ne $seed -or $closure.arm -ne $arm -or
          $closure.native_outcome -ne 'zero_error_reviewed_warnings' -or $closure.error -or
          -not $closure.report_present -or $closure.conversion.errors -ne 0 -or $closure.conversion.notes -ne 0) {
        throw "existing run not accepted: $id"
      }
      Write-Output "verified $id"
      continue
    }
    $remote='powershell.exe -NoProfile -ExecutionPolicy Bypass -File "'+$runner+'" -RunId '+$id+' -Arm '+$arm+' -Seed '+$seed
    & ssh.exe -o BatchMode=yes -o ConnectTimeout=5 -o IdentitiesOnly=yes -i $key user@localhost $remote
    if ($LASTEXITCODE -ne 0) { throw "SSH native run failed: $id exit=$LASTEXITCODE" }
    $closure=Get-Content -LiteralPath (Join-Path $run 'closure.json') -Raw | ConvertFrom-Json
    if ($closure.run_id -ne $id -or $closure.seed -ne $seed -or $closure.arm -ne $arm -or
        $closure.native_outcome -ne 'zero_error_reviewed_warnings' -or $closure.error -or
        -not $closure.report_present -or $closure.conversion.errors -ne 0 -or $closure.conversion.notes -ne 0) {
      throw "native run not accepted: $id"
    }
    Write-Output "accepted $id"
  }
}

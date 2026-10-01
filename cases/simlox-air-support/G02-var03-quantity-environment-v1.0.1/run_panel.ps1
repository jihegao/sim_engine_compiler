$ErrorActionPreference = 'Stop'
$case = (Resolve-Path $PSScriptRoot).Path
$runner = Join-Path $case 'run_native_ssh.ps1'
$variants = @('baseline','qty-two','env-two')
foreach ($seed in 2..13) {
  foreach ($variant in $variants) {
    $runId = 'g02-var03-seed{0:d2}-{1}-20261002-01' -f $seed,$variant
    $run = Join-Path (Join-Path $case 'runs') $runId
    if (-not (Test-Path -LiteralPath $run)) {
      $remote = 'powershell -NoProfile -ExecutionPolicy Bypass -File "{0}" -Variant {1} -Seed {2} -RunId {3}' -f $runner,$variant,$seed,$runId
      $sshOutput = & ssh -tt -o BatchMode=yes -o ConnectTimeout=10 localhost $remote 2>&1
      if ($LASTEXITCODE -ne 0) { throw "SSH failed for $runId : $sshOutput" }
    }
    $closurePath = Join-Path $run 'closure.json'
    if (-not (Test-Path -LiteralPath $closurePath)) { throw "closure absent for $runId" }
    $closure = Get-Content -LiteralPath $closurePath -Raw | ConvertFrom-Json
    $invocation = Get-Content -LiteralPath (Join-Path $run 'invocation.json') -Raw | ConvertFrom-Json
    $steps = @(Get-Content -LiteralPath (Join-Path $run 'steps.json') -Raw | ConvertFrom-Json)
    $roundtrip = Get-Content -LiteralPath (Join-Path $run 'roundtrip-validation.json') -Raw | ConvertFrom-Json
    if ($closure.error -or @($closure.raw.PSObject.Properties).Count -ne 12 -or
        $invocation.seed -ne $seed -or $invocation.variant -ne $variant -or
        $steps.Count -ne 5 -or @($steps | Where-Object status -ne 'completed').Count -ne 0 -or
        -not $roundtrip.passed) { throw "evidence incomplete for $runId" }
    Write-Output "COMPLETE $runId"
  }
}

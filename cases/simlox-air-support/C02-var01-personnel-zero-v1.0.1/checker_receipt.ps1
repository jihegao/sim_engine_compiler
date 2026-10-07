function Assert-CheckerVerdict([string]$name,[string]$stdout,[string]$expectedRunId,
                               [string]$expectedInputSha,[string]$expectedExportSha) {
  if (-not (Test-Path -LiteralPath $stdout -PathType Leaf)) { throw 'checker JSON stdout absent' }
  $verdict = Get-Content -LiteralPath $stdout -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($verdict.passed -isnot [bool] -or -not $verdict.passed) { throw "$name checker JSON does not pass" }
  if ($name -eq 'check_import_export') {
    if ($verdict.schema -ne 'c02-var01-v101-roundtrip/v1' -or
        $verdict.authored_row_tables -isnot [int] -or $verdict.authored_row_tables -ne 20 -or
        @($verdict.issues).Count -ne 0 -or $verdict.input_sha256 -ne $expectedInputSha -or
        $expectedExportSha -notmatch '^[0-9a-f]{64}$' -or
        $verdict.export_sha256 -ne $expectedExportSha) { throw 'roundtrip checker JSON identity differs' }
  } elseif ($name -eq 'check_behavior') {
    if ($verdict.schema -ne 'c02-var01-v101-behavior/v1' -or
        $verdict.run_id -ne $expectedRunId -or $verdict.input_sha256 -ne $expectedInputSha -or
        $verdict.report_cell_checks -isnot [int] -or $verdict.report_cell_checks -ne 10420 -or
        $verdict.parent.cells -isnot [int] -or $verdict.parent.cells -ne 5210 -or
        $verdict.child.cells -isnot [int] -or $verdict.child.cells -ne 5210) {
      throw 'behavior checker JSON identity differs'
    }
  } else { throw "unknown checker stage $name" }
  return $verdict
}

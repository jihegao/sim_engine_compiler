function Assert-CheckerVerdict([string]$name,[string]$stdout,[string]$expectedRunId,[string]$expectedInputSha,[string]$expectedExportSha) {
  if (-not (Test-Path -LiteralPath $stdout -PathType Leaf)) { throw 'checker JSON stdout absent' }
  $verdict = Get-Content -LiteralPath $stdout -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($verdict.passed -isnot [bool] -or -not $verdict.passed) { throw "$name checker JSON does not pass" }
  if ($name -eq 'check_import_export') {
    if ($verdict.schema -ne 'c09-var02-v107-roundtrip/v1' -or $verdict.arm -ne 'shortage' -or
        $verdict.authored_row_tables -isnot [int] -or $verdict.authored_row_tables -ne 25 -or
        @($verdict.issues).Count -ne 0 -or $verdict.source_sha256 -ne $expectedInputSha -or
        $expectedExportSha -notmatch '^[0-9a-f]{64}$' -or
        $verdict.export_sha256 -ne $expectedExportSha) { throw 'roundtrip checker JSON identity differs' }
  } elseif ($name -eq 'check_behavior') {
    if ($verdict.schema -ne 'c09-var02-v107-author-validation/v1' -or
        $verdict.decision -ne 'GO_BOUNDED_PROSPECTIVE_CHILD' -or $verdict.run_id -ne $expectedRunId -or
        $verdict.child_report_cells -isnot [int] -or $verdict.child_report_cells -ne 1754 -or
        $verdict.control_report_cells -isnot [int] -or $verdict.control_report_cells -ne 1754 -or
        $verdict.new_native_runs -isnot [int] -or $verdict.new_native_runs -ne 1) {
      throw 'behavior checker JSON identity differs'
    }
  } else { throw "unknown checker stage $name" }
  return $verdict
}

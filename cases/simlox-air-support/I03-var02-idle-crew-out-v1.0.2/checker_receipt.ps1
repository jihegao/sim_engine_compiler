function Assert-CheckerVerdict([string]$name,[string]$stdout,[string]$expectedRunId,
                               [string]$expectedInputSha,[string]$expectedExportSha) {
  if (-not (Test-Path -LiteralPath $stdout -PathType Leaf)) { throw 'checker JSON stdout absent' }
  $verdict = Get-Content -LiteralPath $stdout -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($verdict.passed -isnot [bool] -or -not $verdict.passed) { throw "$name checker JSON does not pass" }
  if ($name -eq 'check_import_export') {
    if ($verdict.schema -ne 'i03-var02-v102-roundtrip/v1' -or
        $verdict.row_containing_tables -isnot [int] -or $verdict.row_containing_tables -ne 21 -or
        $verdict.table_objects -isnot [int] -or $verdict.table_objects -ne 32 -or
        $verdict.all_null_placeholder_tables -isnot [int] -or $verdict.all_null_placeholder_tables -ne 11 -or
        @($verdict.issues).Count -ne 0 -or $verdict.input_sha256 -ne $expectedInputSha -or
        $expectedExportSha -notmatch '^[0-9a-f]{64}$' -or
        $verdict.export_sha256 -ne $expectedExportSha) { throw 'roundtrip checker JSON identity differs' }
  } elseif ($name -eq 'check_behavior') {
    if ($verdict.schema -ne 'i03-var02-v102-behavior/v1' -or
        $verdict.run_id -ne $expectedRunId -or $verdict.input_sha256 -ne $expectedInputSha -or
        $verdict.report_cell_checks -isnot [int] -or $verdict.report_cell_checks -ne 5210 -or
        $verdict.typed_event_records -isnot [int] -or $verdict.typed_event_records -le 0 -or
        $verdict.timeline.terminal_free_crew -isnot [int] -or $verdict.timeline.terminal_free_crew -ne 1) {
      throw 'behavior checker JSON identity differs'
    }
  } else { throw "unknown checker stage $name" }
  return $verdict
}

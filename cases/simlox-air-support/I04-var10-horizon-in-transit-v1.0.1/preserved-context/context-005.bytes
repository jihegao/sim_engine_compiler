function Assert-CheckerVerdict([string]$name,[string]$stdout,[string]$expectedRunId,
                               [string]$expectedInputSha,[string]$expectedExportSha) {
  if (-not (Test-Path -LiteralPath $stdout -PathType Leaf)) { throw 'checker JSON stdout absent' }
  $verdict = Get-Content -LiteralPath $stdout -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($verdict.passed -isnot [bool] -or -not $verdict.passed) { throw "$name checker JSON does not pass" }
  if ($name -eq 'check_import_export') {
    if ($verdict.schema -ne 'i04-var05-zero-between-roundtrip/v102' -or
        $verdict.tables -isnot [int] -or $verdict.tables -ne 34 -or
        $verdict.authored_rows -isnot [int] -or $verdict.authored_rows -ne 22 -or
        $verdict.exported_rows -isnot [int] -or $verdict.exported_rows -ne 40 -or
        $verdict.authored_cells -isnot [int] -or $verdict.authored_cells -ne 223 -or
        $verdict.exported_cells -isnot [int] -or $verdict.exported_cells -ne 407 -or
        $verdict.all_null_placeholder_tables -isnot [int] -or $verdict.all_null_placeholder_tables -ne 18 -or
        @($verdict.issues).Count -ne 0 -or $verdict.input_sha256 -ne $expectedInputSha -or
        $expectedExportSha -notmatch '^[0-9a-f]{64}$' -or
        $verdict.export_sha256 -ne $expectedExportSha) { throw 'roundtrip checker JSON identity differs' }
  } elseif ($name -eq 'check_behavior') {
    if ($verdict.schema -ne 'i04-var05-zero-between-behavior/v102' -or
        $verdict.run_id -ne $expectedRunId -or $verdict.input_sha256 -ne $expectedInputSha -or
        $verdict.native_run_directory -cne [string](Split-Path -Parent $stdout) -or
        $verdict.export_sha256 -ne $expectedExportSha -or
        @($verdict.issues).Count -ne 0 -or
        $verdict.report_cell_checks -isnot [int] -or $verdict.report_cell_checks -ne 4044 -or
        $verdict.paired_differences -isnot [int] -or $verdict.paired_differences -ne 3 -or
        $verdict.timed_event_records -isnot [int] -or
        $verdict.timed_event_records -notin @(104,105,106) -or
        $verdict.log_lines -isnot [int] -or
        $verdict.log_lines -notin @(118,119,120,121) -or
        $verdict.terminal.ready_edges -isnot [int] -or $verdict.terminal.ready_edges -ne 12 -or
        $verdict.terminal.source_ready_terminal -isnot [int] -or $verdict.terminal.source_ready_terminal -ne 0 -or
        $verdict.terminal.target_ready_terminal -isnot [int] -or $verdict.terminal.target_ready_terminal -ne 2 -or
        $verdict.terminal.transit_terminal -isnot [int] -or $verdict.terminal.transit_terminal -ne 0 -or
        $verdict.terminal.assigned_terminal -isnot [int] -or $verdict.terminal.assigned_terminal -ne 0) {
      throw 'behavior checker JSON identity differs'
    }
  } else { throw "unknown checker stage $name" }
  return $verdict
}

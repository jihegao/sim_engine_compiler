function Assert-CheckerVerdict([string]$name,[string]$stdout,[string]$expectedRunId,
                               [string]$expectedInputSha,[string]$expectedExportSha) {
  if (-not (Test-Path -LiteralPath $stdout -PathType Leaf)) { throw 'checker JSON stdout absent' }
  $verdict = Get-Content -LiteralPath $stdout -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($verdict.passed -isnot [bool] -or -not $verdict.passed) { throw "$name checker JSON does not pass" }
  if ($name -eq 'check_import_export') {
    $expectedKeys=@('schema','passed','run_id','native_run_directory','tables','authored_rows','exported_rows','authored_cells','exported_cells','all_null_placeholder_tables','issues','input_sha256','export_sha256')
    $observedKeys=@($verdict.PSObject.Properties.Name)
    if (@($observedKeys|Where-Object{$_ -notin $expectedKeys}).Count -ne 0 -or $observedKeys.Count -ne $expectedKeys.Count -or
        $verdict.schema -ne 'i04-var10-horizon-transit-roundtrip/v101' -or
        $verdict.run_id -cne $expectedRunId -or
        $verdict.native_run_directory -isnot [string] -or
        $verdict.native_run_directory -cne [string](Split-Path -Parent $stdout) -or
        $verdict.tables -isnot [int] -or $verdict.tables -ne 34 -or
        $verdict.authored_rows -isnot [int] -or $verdict.authored_rows -ne 21 -or
        $verdict.exported_rows -isnot [int] -or $verdict.exported_rows -ne 39 -or
        $verdict.authored_cells -isnot [int] -or $verdict.authored_cells -ne 211 -or
        $verdict.exported_cells -isnot [int] -or $verdict.exported_cells -ne 395 -or
        $verdict.all_null_placeholder_tables -isnot [int] -or $verdict.all_null_placeholder_tables -ne 18 -or
        @($verdict.issues).Count -ne 0 -or $verdict.input_sha256 -ne $expectedInputSha -or
        $expectedExportSha -notmatch '^[0-9a-f]{64}$' -or
        $verdict.export_sha256 -ne $expectedExportSha) { throw 'roundtrip checker JSON identity differs' }
  } elseif ($name -eq 'check_behavior') {
    $expectedKeys=@('schema','passed','run_id','native_run_directory','input_sha256','export_sha256','report_cell_checks','timed_event_records','log_lines','terminal','issues','native_calls')
    $observedKeys=@($verdict.PSObject.Properties.Name)
    if (@($observedKeys|Where-Object{$_ -notin $expectedKeys}).Count -ne 0 -or $observedKeys.Count -ne $expectedKeys.Count -or
        $verdict.schema -ne 'i04-var10-horizon-transit-behavior/v101' -or
        $verdict.run_id -ne $expectedRunId -or $verdict.input_sha256 -ne $expectedInputSha -or
        $verdict.native_run_directory -isnot [string] -or
        $verdict.native_run_directory -cne [string](Split-Path -Parent $stdout) -or
        $verdict.export_sha256 -ne $expectedExportSha -or
        @($verdict.issues).Count -ne 0 -or
        $verdict.report_cell_checks -isnot [int] -or $verdict.report_cell_checks -ne 1244 -or
        $verdict.timed_event_records -isnot [int] -or $verdict.timed_event_records -ne 53 -or
        $verdict.log_lines -isnot [int] -or $verdict.log_lines -ne 61 -or
        $verdict.terminal.microstates -isnot [int] -or $verdict.terminal.microstates -ne 53 -or
        $verdict.terminal.source_ready_terminal -isnot [int] -or $verdict.terminal.source_ready_terminal -ne 0 -or
        $verdict.terminal.target_ready_terminal -isnot [int] -or $verdict.terminal.target_ready_terminal -ne 1 -or
        $verdict.terminal.transit_terminal -isnot [int] -or $verdict.terminal.transit_terminal -ne 1 -or
        $verdict.terminal.assigned_terminal -isnot [int] -or $verdict.terminal.assigned_terminal -ne 0 -or
        $verdict.native_calls -isnot [int] -or $verdict.native_calls -ne 0) {
      throw 'behavior checker JSON identity differs'
    }
  } else { throw "unknown checker stage $name" }
  return $verdict
}

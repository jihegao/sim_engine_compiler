function Assert-CheckerVerdict([string]$name,[string]$stdout,[string]$expectedRunId,
                               [string]$expectedRunDir,[string]$expectedInputSha,
                               [string]$expectedExportSha) {
  if (-not (Test-Path -LiteralPath $stdout -PathType Leaf)) { throw 'checker JSON stdout absent' }
  $verdict = Get-Content -LiteralPath $stdout -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($verdict.passed -isnot [bool] -or -not $verdict.passed -or
      $verdict.run_id -cne $expectedRunId -or
      $verdict.native_run_directory -isnot [string] -or
      $verdict.native_run_directory -cne $expectedRunDir -or
      $verdict.input_sha256 -cne $expectedInputSha -or
      $verdict.export_sha256 -cne $expectedExportSha -or
      @($verdict.issues).Count -ne 0 -or
      $verdict.native_calls -isnot [int] -or $verdict.native_calls -ne 0) {
    throw "$name checker identity differs"
  }
  if ($name -eq 'check_import_export') {
    Assert-JsonKeys $verdict @('schema','passed','run_id','native_run_directory','input_sha256',
      'export_sha256','authored_tables','authored_rows','authored_cells','exported_tables',
      'exported_rows','exported_cells','native_calls','issues') 'roundtrip checker'
    if ($verdict.schema -cne 'e02-var02-roundtrip-check/v104' -or
        $verdict.authored_tables -isnot [int] -or $verdict.authored_tables -ne 31 -or
        $verdict.authored_rows -isnot [int] -or $verdict.authored_rows -ne 24 -or
        $verdict.authored_cells -isnot [int] -or $verdict.authored_cells -ne 274 -or
        $verdict.exported_tables -isnot [int] -or $verdict.exported_tables -ne 31 -or
        $verdict.exported_rows -isnot [int] -or $verdict.exported_rows -ne 35 -or
        $verdict.exported_cells -isnot [int] -or $verdict.exported_cells -ne 369) {
      throw 'roundtrip checker topology differs'
    }
  } elseif ($name -eq 'check_behavior') {
    Assert-JsonKeys $verdict @('schema','passed','run_id','native_run_directory','input_sha256',
      'export_sha256','log_sha256','report_sha256','physical_log_lines','timed_log_lines',
      'report_typed_cells','authored_cells','exported_cells','second_mission_cancel_hour',
      'repair_complete_hour','aircraft_ready_hour','third_mission_success_hour',
      'native_calls','issues') 'behavior checker'
    if ($verdict.schema -cne 'e02-var02-native-behavior-check/v104' -or
        $verdict.log_sha256 -notmatch '^[0-9a-f]{64}$' -or
        $verdict.report_sha256 -notmatch '^[0-9a-f]{64}$' -or
        $verdict.physical_log_lines -isnot [int] -or $verdict.physical_log_lines -ne 123 -or
        $verdict.timed_log_lines -isnot [int] -or $verdict.timed_log_lines -ne 99 -or
        $verdict.report_typed_cells -isnot [int] -or $verdict.report_typed_cells -ne 4044 -or
        $verdict.authored_cells -isnot [int] -or $verdict.authored_cells -ne 274 -or
        $verdict.exported_cells -isnot [int] -or $verdict.exported_cells -ne 369 -or
        $verdict.second_mission_cancel_hour -ne 20.3333 -or
        $verdict.repair_complete_hour -ne 20.9167 -or
        $verdict.aircraft_ready_hour -ne 21.25 -or
        $verdict.third_mission_success_hour -ne 34) {
      throw 'behavior checker bounded receipt differs'
    }
  } else { throw "unknown checker stage $name" }
  return $verdict
}

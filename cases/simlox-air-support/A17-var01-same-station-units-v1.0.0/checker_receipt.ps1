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
    if ($verdict.schema -cne 'a17-var01-roundtrip-check/v1' -or
        $verdict.authored_tables -isnot [int] -or $verdict.authored_tables -ne 33 -or
        $verdict.authored_rows -isnot [int] -or $verdict.authored_rows -ne 20 -or
        $verdict.authored_cells -isnot [int] -or $verdict.authored_cells -ne 203 -or
        $verdict.exported_tables -isnot [int] -or $verdict.exported_tables -ne 33 -or
        $verdict.exported_rows -isnot [int] -or $verdict.exported_rows -ne 38 -or
        $verdict.exported_cells -isnot [int] -or $verdict.exported_cells -ne 387) {
      throw 'roundtrip checker topology differs'
    }
  } elseif ($name -eq 'check_behavior') {
    Assert-JsonKeys $verdict @('schema','passed','run_id','native_run_directory','input_sha256',
      'export_sha256','log_sha256','report_sha256','full_log_lines','timed_log_lines',
      'log_arm','report_typed_cells','exported_cells','ready_by_unit','native_calls','issues') 'behavior checker'
    Assert-JsonKeys $verdict.ready_by_unit @('TEACH-UNIT','TEACH-UNIT-2') 'ready_by_unit'
    if ($verdict.schema -cne 'a17-var01-native-behavior-check/v1' -or
        $verdict.log_sha256 -notmatch '^[0-9a-f]{64}$' -or
        $verdict.report_sha256 -notmatch '^[0-9a-f]{64}$' -or
        $verdict.full_log_lines -isnot [int] -or $verdict.full_log_lines -ne 60 -or
        $verdict.timed_log_lines -isnot [int] -or $verdict.timed_log_lines -ne 52 -or
        $verdict.log_arm -isnot [string] -or
        $verdict.log_arm -cne 'unit0-controller0-return01' -or
        $verdict.report_typed_cells -isnot [int] -or $verdict.report_typed_cells -ne 4044 -or
        $verdict.exported_cells -isnot [int] -or $verdict.exported_cells -ne 387 -or
        $verdict.ready_by_unit.'TEACH-UNIT' -isnot [int] -or
        $verdict.ready_by_unit.'TEACH-UNIT' -ne 1 -or
        $verdict.ready_by_unit.'TEACH-UNIT-2' -isnot [int] -or
        $verdict.ready_by_unit.'TEACH-UNIT-2' -ne 1) {
      throw 'behavior checker bounded receipt differs'
    }
  } else { throw "unknown checker stage $name" }
  return $verdict
}

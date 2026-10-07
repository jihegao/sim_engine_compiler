Set-StrictMode -Version Latest

function Assert-CapturedProcessRecord([object]$record, [int]$requiredSession) {
  if ($null -eq $record -or $record -isnot [System.Collections.IDictionary]) { throw 'capture record absent or malformed' }
  foreach ($key in @('child_pid', 'child_session_id', 'exit_code', 'stdout_path', 'stderr_path')) {
    if (-not $record.Contains($key)) { throw "capture record missing $key" }
  }
  if ($record.child_pid -isnot [int] -or $record.child_pid -le 0) { throw 'child PID not an observed positive integer' }
  if ($record.child_session_id -isnot [int] -or $record.child_session_id -ne $requiredSession) {
    throw 'child session not observed as required integer'
  }
  if ($record.exit_code -isnot [int]) { throw 'child OS exit not observed as integer' }
  foreach ($key in @('stdout_path', 'stderr_path')) {
    if ($record[$key] -isnot [string] -or -not (Test-Path -LiteralPath $record[$key] -PathType Leaf)) {
      throw "capture $key absent"
    }
  }
  return $record
}

function Invoke-CapturedProcess(
  [string]$filePath,
  [string]$argumentString,
  [string]$workingDirectory,
  [string]$stdoutPath,
  [string]$stderrPath,
  [int]$requiredSession = 0
) {
  if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) { throw "child executable absent: $filePath" }
  if (-not (Test-Path -LiteralPath $workingDirectory -PathType Container)) { throw 'child working directory absent' }
  foreach ($path in @($stdoutPath, $stderrPath)) {
    $parent = Split-Path -Parent $path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw "capture directory absent: $parent" }
    if (Test-Path -LiteralPath $path) { throw "capture path already exists: $path" }
  }
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $filePath
  $psi.Arguments = $argumentString
  $psi.WorkingDirectory = $workingDirectory
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.StandardOutputEncoding = New-Object System.Text.UTF8Encoding($false)
  $psi.StandardErrorEncoding = New-Object System.Text.UTF8Encoding($false)
  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = $psi
  $started = $false
  try {
    $started = $process.Start()
    if (-not $started) { throw 'OS child start returned false' }
    $childPid = [int]$process.Id
    try { $childSession = [int]$process.SessionId } catch { throw 'child session unavailable while process handle live' }
    $outTask = $process.StandardOutput.ReadToEndAsync()
    $errTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $outText = $outTask.GetAwaiter().GetResult()
    $errText = $errTask.GetAwaiter().GetResult()
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($stdoutPath, $outText, $utf8)
    [System.IO.File]::WriteAllText($stderrPath, $errText, $utf8)
    $exitCode = $process.ExitCode
    $record = [ordered]@{
      child_pid = $childPid
      child_session_id = $childSession
      exit_code = $exitCode
      stdout_path = $stdoutPath
      stderr_path = $stderrPath
    }
    Assert-CapturedProcessRecord $record $requiredSession | Out-Null
    return $record
  } finally {
    $process.Dispose()
  }
}

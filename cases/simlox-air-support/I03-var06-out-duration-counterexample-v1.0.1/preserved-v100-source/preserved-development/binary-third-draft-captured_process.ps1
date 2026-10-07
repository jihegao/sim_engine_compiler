Set-StrictMode -Version Latest

function Get-CapturedFileSha([string]$path) {
  $stream=[System.IO.File]::OpenRead($path)
  $hasher=[System.Security.Cryptography.SHA256]::Create()
  try { return ([BitConverter]::ToString($hasher.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
  finally { $stream.Dispose(); $hasher.Dispose() }
}

function Assert-CapturedProcessRecord([object]$record, [int]$requiredSession) {
  if ($null -eq $record -or $record -isnot [System.Collections.IDictionary]) { throw 'capture record absent' }
  foreach ($key in @('child_pid','child_session_id','exit_code','stdout_path','stderr_path',
                     'stdout_bytes','stderr_bytes','stdout_sha256','stderr_sha256','capture_error')) {
    if (-not $record.Contains($key)) { throw "capture record missing $key" }
  }
  if ($record.child_pid -isnot [int] -or $record.child_pid -le 0) { throw 'PID not observed as positive integer' }
  if ($record.child_session_id -isnot [int] -or $record.child_session_id -ne $requiredSession) {
    throw 'child session not observed as required integer'
  }
  if ($record.exit_code -isnot [int]) { throw 'OS exit not observed as integer' }
  if ($null -ne $record.capture_error) { throw "child capture failed: $($record.capture_error)" }
  foreach ($kind in @('stdout','stderr')) {
    $path=$record[$kind + '_path']
    if ($path -isnot [string] -or -not (Test-Path -LiteralPath $path -PathType Leaf)) {
      throw "$kind original byte stream absent"
    }
    $file=Get-Item -LiteralPath $path
    $sha=Get-CapturedFileSha $path
    if ($record[$kind + '_bytes'] -isnot [long] -or $record[$kind + '_bytes'] -ne $file.Length -or
        $record[$kind + '_sha256'] -ne $sha) { throw "$kind original byte stream seal differs" }
  }
  return $record
}

function Assert-SuccessfulCapture([object]$record,[int]$requiredSession) {
  Assert-CapturedProcessRecord $record $requiredSession | Out-Null
  if ($record.exit_code -ne 0) { throw "child OS exit=$($record.exit_code)" }
  return $record
}

function Invoke-CapturedProcess(
  [string]$filePath,[string]$argumentString,[string]$workingDirectory,
  [string]$stdoutPath,[string]$stderrPath,[int]$requiredSession=0,
  [bool]$testForceSessionFailure=$false,[bool]$testForceDrainSetupFailure=$false
) {
  if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) { throw "child executable absent: $filePath" }
  if (-not (Test-Path -LiteralPath $workingDirectory -PathType Container)) { throw 'working directory absent' }
  foreach ($path in @($stdoutPath,$stderrPath)) {
    if (-not (Test-Path -LiteralPath (Split-Path -Parent $path) -PathType Container) -or
        (Test-Path -LiteralPath $path)) { throw "capture path missing parent or already exists: $path" }
  }
  $psi=New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName=$filePath; $psi.Arguments=$argumentString; $psi.WorkingDirectory=$workingDirectory
  $psi.UseShellExecute=$false; $psi.CreateNoWindow=$true
  $psi.WindowStyle=[System.Diagnostics.ProcessWindowStyle]::Hidden
  $psi.RedirectStandardOutput=$true; $psi.RedirectStandardError=$true
  $proc=New-Object System.Diagnostics.Process
  $proc.StartInfo=$psi
  $outFile=$null; $errFile=$null; $outTask=$null; $errTask=$null
  $started=$false; $pidObserved=$null; $sessionObserved=$null; $exitObserved=$null; $captureError=$null
  try {
    $outFile=New-Object System.IO.FileStream($stdoutPath,[System.IO.FileMode]::CreateNew,
      [System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
    $errFile=New-Object System.IO.FileStream($stderrPath,[System.IO.FileMode]::CreateNew,
      [System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
    $started=$proc.Start()
    if (-not $started) { throw 'OS child start returned false' }
    $pidObserved=[int]$proc.Id
    # Start both binary drains before waiting; a setup error is retained, then
    # retried against the original file stream. A failed retry is handled below.
    try {
      if ($testForceDrainSetupFailure) { throw 'injected post-Start stdout drain setup failure' }
      $outTask=$proc.StandardOutput.BaseStream.CopyToAsync($outFile)
    } catch {
      $captureError=$_.Exception.Message
      try { $outTask=$proc.StandardOutput.BaseStream.CopyToAsync($outFile) }
      catch { $captureError += "; stdout retry: $($_.Exception.Message)" }
    }
    try { $errTask=$proc.StandardError.BaseStream.CopyToAsync($errFile) }
    catch { $captureError += "; stderr setup: $($_.Exception.Message)" }
    try {
      if ($testForceSessionFailure) { throw 'injected post-Start session observation failure' }
      $sessionObserved=[int]$proc.SessionId
    } catch { $captureError += "; session: $($_.Exception.Message)" }
  } catch {
    if ($null -eq $captureError) { $captureError=$_.Exception.Message }
  } finally {
    if ($started) {
      # Even observation or drain failure must join the child naturally before caller releases mutex.
      try {
        if ($null -eq $outTask) {
          try { $outTask=$proc.StandardOutput.BaseStream.CopyToAsync($outFile) }
          catch {
            $captureError += "; stdout fallback: $($_.Exception.Message)"
            try { $outTask=$proc.StandardOutput.BaseStream.CopyToAsync([System.IO.Stream]::Null) }
            catch { $captureError += "; stdout discard-drain: $($_.Exception.Message)" }
          }
        }
        if ($null -eq $errTask) {
          try { $errTask=$proc.StandardError.BaseStream.CopyToAsync($errFile) }
          catch {
            $captureError += "; stderr fallback: $($_.Exception.Message)"
            try { $errTask=$proc.StandardError.BaseStream.CopyToAsync([System.IO.Stream]::Null) }
            catch { $captureError += "; stderr discard-drain: $($_.Exception.Message)" }
          }
        }
      } finally {
        # A failed fallback cannot bypass this join or release the caller's mutex.
        $proc.WaitForExit()
      }
      if ($null -ne $outTask) {
        try { [void]$outTask.GetAwaiter().GetResult() }
        catch { $captureError += "; stdout drain: $($_.Exception.Message)" }
      }
      if ($null -ne $errTask) {
        try { [void]$errTask.GetAwaiter().GetResult() }
        catch { $captureError += "; stderr drain: $($_.Exception.Message)" }
      }
      $exitObserved=[int]$proc.ExitCode
    }
    if ($null -ne $outFile) { $outFile.Dispose() }
    if ($null -ne $errFile) { $errFile.Dispose() }
    $proc.Dispose()
  }
  $outInfo=Get-Item -LiteralPath $stdoutPath -ErrorAction SilentlyContinue
  $errInfo=Get-Item -LiteralPath $stderrPath -ErrorAction SilentlyContinue
  return [ordered]@{
    child_pid=$pidObserved; child_session_id=$sessionObserved; exit_code=$exitObserved
    stdout_path=$stdoutPath; stderr_path=$stderrPath
    stdout_bytes=$(if ($outInfo) { [long]$outInfo.Length } else { $null })
    stderr_bytes=$(if ($errInfo) { [long]$errInfo.Length } else { $null })
    stdout_sha256=$(if ($outInfo) { Get-CapturedFileSha $stdoutPath } else { $null })
    stderr_sha256=$(if ($errInfo) { Get-CapturedFileSha $stderrPath } else { $null })
    capture_error=$captureError
  }
}

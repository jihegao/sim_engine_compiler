param([string]$RunId)
[IO.File]::WriteAllText('C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\A08-var05-integer-count-v1.0.0\runs\wrapper-started.txt', 'wrapper started')
& 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\A08-var05-integer-count-v1.0.0\run_native_seed_matrix_ssh.ps1' -RunId $RunId

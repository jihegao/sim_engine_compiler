# D13.var03: time-varying MAXPM profile

This paired SIMLOX 2017 case derives from the accepted [static MAXPM=2 case](../D13-var02-maxpm-two-v1.0.0/README.md). Both arms have two aircraft, one local CAL24 PM, three scheduled missions, seed 1, and a 36-hour horizon. `Unit.MAXPMP=CAP24` selects three explicit `MaxPMProfile` periods: capacity 0 until hour 24.25, capacity 1 until 24.75, then capacity 2 in the [rise input](rise-input.json) versus 1 in the [hold input](hold-input.json). Only that final profile value and descriptive text differ. The [builder](build.py) pins the accepted parent; the [contract](contract.json) freezes the claim and gate.

Both arms create two CAL24 task objects at hour 24 and start physical work on one aircraft at 24.25. At 24.75, the rise arm starts the second aircraft before the first completes; the hold arm waits until the first completes at 25.25. See the [bounded sign-off](cli-scope-signoff-2026-10-04.md) for report reconciliation and limits.

The [guarded runner](run_native_ssh.ps1) uses session-0 SSH, `Global\SimloxIssue18NativeQueue`, GUI PID 13340/session 1 checks, and a targeted 60-second child watchdog. Its raw run is ignored by Git; the [evidence index](evidence-index.json) publishes sizes and SHA-256 hashes for 22 files. The [author replay](validate_native.py) and separately written [independent replay](review/independent_replay.py) verify sealed evidence without invoking SIMLOX.

Read-only author replay:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\cases\simlox-air-support\D13-var03-dynamic-maxpm-v1.0.0\validate_native.py
```

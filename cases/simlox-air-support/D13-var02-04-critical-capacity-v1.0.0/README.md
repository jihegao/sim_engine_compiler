# D13.var02/04: critical PM at zero MAXPM capacity

This paired SIMLOX 2017 case derives from the accepted [D13 MAXPM=2 case](../D13-var02-maxpm-two-v1.0.0/README.md) and uses the accepted [PMActivation schema](../D13-var01-pm-activation-v1.0.0/README.md). Both arms have two aircraft, three scheduled missions, one local CAL24 PM, `Unit.MAXPM=0`, `CAL24.DTIM=0.1`, and global and local PM enablement. Only `PMActivation.CRIT=Y/N` and descriptive text differ between the [Y input](y-input.json) and [N input](n-input.json). The [builder](build.py) pins the parent and template bytes; the [contract](contract.json) freezes the claim and gate.

Both arms create CAL24 PM task objects at hour 24. With `CRIT=Y`, both aircraft physically perform PM from 26.4 to 27.4 hours despite `MAXPM=0`. With `CRIT=N`, neither PM physically works through the 36-hour horizon; a pending task pauses for the third mission and continues afterward. See the [bounded sign-off](cli-scope-signoff-2026-10-04.md) for report reconciliation and limits.

The [guarded runner](run_native_ssh.ps1) uses session-0 SSH, `Global\SimloxIssue18NativeQueue`, GUI PID 13340/session 1 checks, and a targeted 60-second child watchdog. Its raw run is ignored by Git; the [evidence index](evidence-index.json) publishes sizes and SHA-256 hashes for its 22 files. The [author replay](validate_native.py) and separately written [independent replay](review/independent_replay.py) verify the sealed run without invoking SIMLOX.

Read-only author replay:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\cases\simlox-air-support\D13-var02-04-critical-capacity-v1.0.0\validate_native.py
```

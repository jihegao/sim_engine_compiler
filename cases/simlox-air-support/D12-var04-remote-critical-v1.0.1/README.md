# D12.var04: critical small PM at a remote base

This paired SIMLOX 2017 case derives from the accepted [D12.var01 active-small linked case](../D12-var01-active-small-v1.0.0/README.md). Both arms use two aircraft, a critical `CAL24` PM, a related noncritical `BIG24P75` PM, two maintenance workers at each base, and 0.25-hour transport each way. Only the [local input](local-input.json) versus [remote input](remote-input.json) `CAL24 PMLocation.STID` and descriptive text differ. The [builder](build.py) verifies their frozen bytes against the accepted parent; the [contract](contract.json) states the exposure and acceptance gate.

The native logs show local `CAL24` work interrupted at hour 24.75 as `BIG24P75` starts. At BASE-02, both `CAL24` tasks physically work 24.25–25.25, return to BASE-01 at 25.5, and `BIG24P75` starts at 25.5. The log does not expose an internal stop attempt in the remote arm. See the [bounded sign-off](cli-scope-signoff-2026-10-04.md) for report reconciliation and limits.

The [guarded runner](run_native_ssh.ps1) uses session-0 SSH, `Global\SimloxIssue18NativeQueue`, GUI PID 13340/session 1 checks and a targeted 60-second child watchdog. Its immutable raw run is ignored by Git; the [evidence index](evidence-index.json) publishes sizes and SHA-256 hashes for all 22 raw files. The [author replay](validate_native.py) and separately written [independent replay](review/independent_replay.py) inspect sealed output without invoking SIMLOX. Earlier [v1.0.0](../D12-var04-remote-critical-v1.0.0/README.md) remains an excluded unequal-worker diagnostic.

Read-only author replay:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\cases\simlox-air-support\D12-var04-remote-critical-v1.0.1\validate_native.py
```

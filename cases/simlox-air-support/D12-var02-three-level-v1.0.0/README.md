# D12.var02: three-level calendar PM relation

This paired SIMLOX 2017 case derives from the accepted [active-small D12.var01 case](../D12-var01-active-small-v1.0.0/README.md). It retains `BIG48P5.PMRID=CAL24`, then adds `TOP49` due at hour 49 with a one-hour task using the sole `P-MAINT` worker. The [unlinked input](unlinked-input.json) leaves `TOP49.PMRID` null; the [linked input](linked-input.json) names `BIG48P5`. Description is the only other difference between arms. Both use two aircraft, seed 1, one replication and a 60-hour horizon.

At hour 48.5, the existing BIG48P5→CAL24 relation stops the performing CAL24 task on aircraft 1 in both arms. BIG48P5 then holds the worker through hour 49. At hour 49, linked TOP49 explicitly stops that performing middle task and releases its worker; a second middle task starts and stops at the same timestamp. The unlinked control completes both middle tasks. The [sign-off](cli-scope-signoff-2026-10-04.md) gives the measured counts and limits. A CAL24 task also stops at hour 49 in the linked arm, but this pair cannot isolate automatic transitive cancellation.

The [guarded runner](run_native_ssh.ps1) uses session-0 SSH, `Global\SimloxIssue18NativeQueue`, GUI PID 13340/session 1 checks and a targeted 60-second child watchdog. Its immutable raw run remains under ignored `runs/`; the [evidence index](evidence-index.json) publishes all 22 raw file sizes and SHA-256 hashes. The [author replay](validate_native.py) and separately written [independent replay](review/independent_replay.py) inspect the sealed output without invoking SIMLOX again.

Read-only author replay:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\cases\simlox-air-support\D12-var02-three-level-v1.0.0\validate_native.py
```

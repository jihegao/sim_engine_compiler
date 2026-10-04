# D12.var03: ENFNC changes noncritical repair and PM work order

This paired SIMLOX 2017 case derives from the accepted [D08.var03 explicit noncritical failure model](../D08-var03-criticality-v1.0.0/README.md) and uses the [D05 shared maintenance worker pattern](../D05-maintenance-competition-v1.0.0/README.md). Both arms have one h8–10 mission, explicit `FM-POS-A.CRITF=0`, a 9.9-hour noncritical calendar PM, a half-hour direct repair, a one-hour PM and one `P-MAINT` worker. The [N input](n-input.json) and [Y input](y-input.json) differ only in descriptive text and `PM9P9.ENFNC`.

The native logs show the same noncritical failure at hour 8.31325 and both PM and repair pending at the hour-10 return. With ENFNC=N, PM physically works 10–11 then CM 11–11.5. With ENFNC=Y, CM works 10–10.5 then PM 10.5–11.5. Both task types emit a start event at hour 10 in both arms; the observed difference is the **physical work order** and shared-worker booking. See the [bounded sign-off](cli-scope-signoff-2026-10-04.md) for report reconciliation and limits.

The [guarded runner](run_native_ssh.ps1) uses session-0 SSH, `Global\SimloxIssue18NativeQueue`, GUI PID 13340/session 1 checks and a targeted 60-second child watchdog. Its immutable raw run is ignored by Git; the [evidence index](evidence-index.json) publishes all 22 raw file sizes and SHA-256 hashes. The [author replay](validate_native.py) and separately written [independent replay](review/independent_replay.py) inspect sealed output without invoking SIMLOX. Earlier [#204](../D12-var03-enfnc-v1.0.0/README.md) and [no-exposure](../D12-var03-enfnc-v1.0.1/README.md) diagnostics remain excluded.

Read-only author replay:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\cases\simlox-air-support\D12-var03-enfnc-v1.0.2\validate_native.py
```

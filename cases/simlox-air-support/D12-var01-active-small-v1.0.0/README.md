# D12.var01: small PM already performing when the larger PM becomes due

This paired case derives directly from the accepted [D12.var01 PM relation](../D12-var01-pm-relation-v1.0.1/README.md). The [builder](build.py) changes the larger PM's first calendar due from hour 47 to hour 48.5, updating its identifiers and description. The two frozen [inputs](unlinked-input.json) otherwise differ only in `BIG48P5.PMRID`: null in the control, `CAL24` in the linked arm.

Both arms have two aircraft, one shared `P-MAINT` worker, `CAL24` due at hour 48, seed 1, one replication and a 60-hour horizon. Native events show a `CAL24` subtask starts performing at hour 48 and still holds the worker at hour 48.5. The linked arm explicitly stops that subtask at hour 48.5, frees the worker and starts `BIG48P5`; a second small task waiting on the other aircraft is stopped before work. The control completes both small PMs. The [sign-off](cli-scope-signoff-2026-10-04.md) states the bounded observation and its limits.

The [guarded runner](run_native_ssh.ps1) uses session-0 SSH, `Global\SimloxIssue18NativeQueue`, GUI PID 13340/session 1 checks and a targeted 60-second child watchdog. The immutable run's 22 task-local raw files remain under ignored `runs/`; the [evidence index](evidence-index.json) lists their sizes and SHA-256 hashes. [Author replay](validate_native.py) and a separately written [independent replay](review/independent_replay.py) verify the sealed outputs without invoking SIMLOX again.

Read-only author replay:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\cases\simlox-air-support\D12-var01-active-small-v1.0.0\validate_native.py
```

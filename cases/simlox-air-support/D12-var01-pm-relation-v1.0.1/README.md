# D12.var01: larger PM related to a smaller calendar PM

This bounded package compares two SIMLOX 2017 command-line models derived from the accepted [D05 maintenance competition](../D05-maintenance-competition-v1.0.0/README.md). Both have two aircraft, one shared `P-MAINT` worker, a 24-hour `CAL24` PM, a 47-hour `BIG47` PM, seed 1, one replication, and a 60-hour horizon. The [contract](contract.json) freezes the source and executable fingerprints. The two [input models](unlinked-input.json) differ only in descriptive text and `BIG47.PMRID`: null in the control, `CAL24` in the linked arm.

The guarded [runner](run_native_ssh.ps1) imports, exports, calculates, and reports each arm in session-0 SSH under `Global\SimloxIssue18NativeQueue`. It checks the existing GUI PID 13340/session 1 before and after each native child, and seals 22 local raw files. The [evidence index](evidence-index.json) names each raw file's size and SHA-256; the files remain under ignored `runs/`. [Author replay](validate_native.py), [independent replay](review/independent_replay.py), and the [sign-off](cli-scope-signoff-2026-10-04.md) document the accepted result.

The linked arm suppresses the two second-cycle small-PM worker-hours seen in the control at hours 49–51. One linked small task is never created; the other starts at hour 48 and is explicitly stopped at hour 49 before performing. This does not demonstrate interruption of an already performing small PM or directly expose reset counters. The earlier v1.0.0 run remains a local diagnostic because its frozen expectation of exact D05 failure timing was false; v1.0.1 corrects that expectation and reruns the same source inputs.

Read-only replay:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\cases\simlox-air-support\D12-var01-pm-relation-v1.0.1\validate_native.py
```

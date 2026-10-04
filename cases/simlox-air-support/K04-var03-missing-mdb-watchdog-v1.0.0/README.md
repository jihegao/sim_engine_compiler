# K04.var03 1.0.0 — missing MDB under a relocated SXI

**Classification: sealed capability-limit diagnostic, not a reusable published case.** The accepted [K04.var02 relative include case](../K04-var02-relative-cwd-v1.0.4/cli-scope-signoff-2026-10-04.md) provides the positive control and the native SXI. This diagnostic copies that SXI byte for byte into a fresh run directory without `level1.mdb`. Its process working directory is the accepted parent's run directory, which does contain `level1.mdb`. The [contract](contract.json) and [runner](run_native_ssh.ps1) freeze those paths and source hashes.

The guarded session-0 SSH runner used `Global\SimloxIssue18NativeQueue`, protected GUI PID 13340/session 1, and restored the original per-user MDB association. It waited 20 seconds, captured the child process and outputs, waited another 25 seconds, captured them again, then verified the exact child PID, session and command line before stopping only that child. It left the protected GUI running.

The log attempted `level1.mdb` under the new SXI directory, where the file was absent. At both checkpoints the same session-0 child was live, its CPU time and file sizes unchanged, `model.sxo` was four bytes, and `model.log` was absent. The watchdog stopped the child after 45 seconds (exit `-1`). There is **no native terminal converter result**. The observation proves a bounded noncompletion through 45 seconds in this installed CLI session; it does not prove an indefinite hang, an interactive dialog, or a general missing-file error rule.

The [author replay](author-diagnostic-validation-2026-10-04.json) checks the source, guard, process, timeout and raw seals. Independent replay and static review are under `review/`. Local raw files remain under ignored `runs/`, with their SHA-256 values in [diagnostic-evidence-index.json](diagnostic-evidence-index.json).

The installed manual describes relative include lookup and a GUI reopen remedy for an unfound include; it does not prescribe this session-0 CLI outcome. GUI file-dialog/MRU behavior, a native missing-file rejection code, other file types, other paths and engines, and full K04.var03 remain unverified. Issue #18 remains open.

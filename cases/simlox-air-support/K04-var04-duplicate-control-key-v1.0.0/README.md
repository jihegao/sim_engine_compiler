# K04.var04: duplicate Control and repeated Station key

This bounded case derives two isolated MDB IncludeFiles conflict arms from the accepted [K04.var01 nested-MDB case](../K04-var01-nested-mdb-include-v1.0.0/cli-scope-signoff-2026-10-04.md). Each main JSON source changes only the parent's sole IncludeFiles path and comment. The first arm includes an MDB with a complete copy of the parent's 24-column Control row plus the required BASE-01 Station row. The second includes two MDB levels, each with a Station row keyed `BASE-01` and a distinct description. No sparse SXI import is used.

The frozen run `k04-var04-duplicate-control-key-v100-ssh-20261004-01` used session-0 SSH, the host-wide `Global\SimloxIssue18NativeQueue`, GUI PID 13340 preservation, exact source fingerprints, x86 Jet MDB generation and x86 ODBC readback. The temporary per-user MDB association for calculations was restored afterward. Raw run files remain under ignored `runs/`; `closure.json` seals 25 of them by SHA-256. An incidental startup `preflight.trace` is ignored and is outside the evidence closure.

The control-arm native log traverses its MDB, inserts one Control and one Station record, then reports sole converter error **#2043, `Table already defined: Control`**. The key-arm log traverses both MDB levels, inserts their Station rows, then reports sole converter error **#2013, `Double definition of data for: BASE-01`**. Each converter completed with one error and emitted only a four-byte SXO placeholder. SIMLOX process exit code zero is therefore not a successful simulation result. No JSON report or event result is accepted for either arm.

Run the author replay, which reads but does not change the sealed run:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\cases\simlox-air-support\K04-var04-duplicate-control-key-v1.0.0\validate_native.py
```

The exact accepted scope and review results are recorded in [the CLI sign-off](cli-scope-signoff-2026-10-04.md). This case does not establish precedence among other table types or keys, a generic merge rule, a usable simulation outcome, GUI behavior, or full K04/Issue #18 completion.

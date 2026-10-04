# K04.var01: nested MDB IncludeFiles chain

This bounded case extends the accepted [K05.var05 one-level MDB include](../K05-var05-runtime-mdb-include-v1.0.2/cli-scope-signoff-2026-10-04.md). The main SXI contains one IncludeFiles row pointing to a task-local `level1.mdb`. That database contains one IncludeFiles row pointing to `level2.mdb`. The second database contains only the required `BASE-01` Station row. The main model retains K02's `K02-NAMED` Station and other accepted business rows, so the resolved business-row union matches the single-file K02 parent apart from IncludeFiles metadata.

The runner requires session-0 SSH, the host-wide `Global\SimloxIssue18NativeQueue`, exact source, parent and contract fingerprints, a fresh run directory, and the active GUI PID 13340. It creates both MDBs using 32-bit Jet and enumerates/readbacks their user tables with 32-bit ODBC. For calculation it temporarily maps the current-user `.mdb` association to the installed 64-bit Access ODBC driver, then restores the original mapping. Databases and native raw artifacts stay under ignored `runs/` and are indexed by SHA-256; they are not committed.

## Frozen run

Run ID: `k04-var01-nested-mdb-v100-ssh-20261004-01`. The immutable run is already complete; the following command documents its guarded invocation:

```powershell
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes 127.0.0.1 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\K04-var01-nested-mdb-include-v1.0.0\run_native_ssh.ps1 -RunId k04-var01-nested-mdb-v100-ssh-20261004-01'
```

Read-only author replay:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\cases\simlox-air-support\K04-var01-nested-mdb-include-v1.0.0\validate_native.py
```

SIMLOX logged the level-1 IncludeFiles row, then the level-2 Station row, each followed by `Data successfully included`. Converter Errors 0, Warnings #108/#126 and Notes 0; SXI and SXO are usable. The event log and raw report are byte-identical to accepted K05/K02. The closure seals 17 local raw files, including both MDBs and their ODBC readbacks. Author replay passed 136 checks; independent review is recorded separately.

The earlier local sparse SXI diagnostic (closure SHA-256 `660911c81d9d33d0d18230f4ce8bcdf35c09c0ad557620412b795b4d32a89f6f`) is excluded: SIMLOX's JSON-to-SXI import synthesized a second default Control table, yielding converter errors and no usable SXO. The current case establishes nested MDB traversal only. Nested SXI/OPI modules, relative and missing paths, duplicate Control/key conflicts, GUI behavior and complete K04 remain unverified.

# K05.var05: Access database runtime include

This bounded case tests SIMLOX 2017 `IncludeFiles` against a task-local Access MDB. It depends on the accepted K02.var01 named Station case. The main model contains K02's `K02-NAMED` Station and all other authored K02 data. The included MDB contains only the required `BASE-01` Station row. The original ProblemDescription is retained so event and report artifacts can be compared byte for byte.

The installed 64-bit SIMLOX has a pre-existing `.mdb` association to the 32-bit-only `Microsoft Access Driver (*.mdb)`. The guarded runner temporarily maps `.mdb` to the installed 64-bit `Microsoft Access Driver (*.mdb, *.accdb)` during calculation and restores the original per-user registry value immediately afterward. The MDB is generated locally through 32-bit Jet, read back through 32-bit ODBC, hashed, and kept under ignored `runs/`. No database or raw native output is committed.

## Frozen native workflow

The runner requires session-0 SSH, the `Global\SimloxIssue18NativeQueue` mutex, the active GUI PID 13340, exact accepted parent/source/tool fingerprints, and a fresh run directory. It creates the MDB, imports the main JSON to SXI, exports that SXI for row inspection, calculates, and exports the raw JSON report. The frozen run ID is `k05-var05-mdb-v102-ssh-20261004-01`.

```powershell
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes 127.0.0.1 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\K05-var05-runtime-mdb-include-v1.0.2\run_native_ssh.ps1 -RunId k05-var05-mdb-v102-ssh-20261004-01'
```

The run is immutable and already complete. Read-only replay:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\cases\simlox-air-support\K05-var05-runtime-mdb-include-v1.0.2\validate_native.py
```

## Bounded result

SIMLOX logged `Station, 1 record inserted`, `Data successfully included`, and `Errors: 0, Warnings: 2, Notes: 0` (reviewed warnings 108 and 126). The resulting SXI and SXO are usable. The native event log SHA-256 is `2d2e6c368305203052e347748dab8f36261947dae6f6a189fad4312e47c0a491`; the raw report SHA-256 is `5a3fd9007de442ce0f7a5210cd61cfe1e3a362774300497020341dc05d478655`. Both are byte-identical to the accepted K02 run. Author replay passed 125 checks; independent review is recorded separately. The original `.mdb` registry association and GUI PID/session/start time were verified after the run.

The earlier v1.0.0 diagnostic failed to open the MDB under the mismatched driver association. The v1.0.1 diagnostic demonstrated inclusion but changed ProblemDescription; it is excluded from this claim. This case establishes only a one-row MDB runtime include through the local driver mapping. K05 editor import/export, aliases and sorting, null merges, invalid values, and broader database types remain unverified. It does not establish the K04 nested or relative file-include variants.

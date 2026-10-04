# K05.var02: ODBC key update with null fields

This bounded case checks database import into an existing SIMLOX input document. It derives a positive control from the accepted K02.var01 model: the two authored Station business rows are kept byte-for-byte but placed together in one unnamed Station instance. The task-local Access MDB then supplies one `BASE-01` Station row with a changed description and database nulls for `QTY` and `TYPE`.

The guarded native runner imports, exports, calculates and reports the baseline before creating a temporary 64-bit user DSN. It creates/readbacks the MDB with 32-bit Jet/ODBC, verifies the same null row through that DSN, imports it into the baseline SXI, removes the DSN before calculation, and exports/calculates/reports the merged SXI. Session-0 SSH, `Global\SimloxIssue18NativeQueue`, GUI PID 13340 and an isolated immutable run directory are required. Raw files remain under ignored `runs/` and are sealed by SHA-256.

Run ID: `k05-var02-odbc-null-v101-ssh-20261004-01`. The native import log says `Station, 1 record updated`. The merged JSON export has one `BASE-01` row: `DESCR` changes to `ODBC merged teaching base`, while `QTY=1` and `TYPE=WS` remain. `K02-NAMED` and every other table remain unchanged. Both converters report Errors 0, Warnings #108/#126 and Notes 0. Baseline and merged event logs and raw JSON reports are byte-identical to each other and to accepted K02; both SXOs are usable. The temporary DSN is absent and the original MDB association remains in place.

Read-only author replay:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\cases\simlox-air-support\K05-var02-odbc-null-merge-v1.0.1\validate_native.py
```

The earlier local v1.0.0 diagnostic used K02's two named Station instances directly. ODBC import inserted `BASE-01` into the default instance, leaving the named `K02-BASE` row in place; the converter rejected that model with #2013 and a four-byte SXO. It is excluded from the accepted null-merge claim. The [CLI sign-off](cli-scope-signoff-2026-10-04.md) records its closure hash and the current case limits. This case does not establish a merge rule for named instances, aliases, ordering, invalid values, other tables, GUI, or all of K05.

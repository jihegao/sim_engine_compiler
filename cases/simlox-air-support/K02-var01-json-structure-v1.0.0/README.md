# K02.var01 v1.0.0: excluded JSON structure diagnostics

This package is a source-frozen **NO-GO** diagnostic, not a publication entry. Both inputs derive from the accepted K01.var04 CLI model and were independently cleared for guarded native capability probes before execution. The [contract](contract.json) and [exact diff](exact-diff.json) record their hypotheses.

The `inactive` arm used `Station.inactive_rows=[1]` after BASE-01 row 0 and K02-INACTIVE row 1. Native export replaced BASE-01 with an all-null row and omitted `inactive_rows`; calculation reported four converter errors, including unknown BASE-01, and produced only a four-byte invalid SXO. Its local closure SHA-256 is `f747cf95b1577bdebdbb27a14556ec1cd77a674d65ef986818d0fdeede209eee` with nine raw seals. This is evidence of one-based row positioning for this input, not a general index rule.

The `named` arm used explicitly named `Station` instances K02-BASE and K02-AUX. Native import, export, calculation and report succeeded with zero errors; the accepted parent log and non-description report rows matched. Export preserved both named instances but prepended an empty default Station instance with one all-null row, violating this version's frozen exact-instance gate. Its local closure SHA-256 is `46462267656e8550e998e99b4f60aba910c3483441b5fbc88284dc2850c80a94` with 12 raw seals.

Both runs used the session-0 SSH guard, host mutex and preserved GUI PID 13340. Raw `.sxi`, `.sxo`, logs and reports remain under ignored `runs/`. [v1.0.1](../K02-var01-json-structure-v1.0.1/README.md) freezes corrected separate gates and uses fresh run IDs; it does not reclassify either v1.0.0 run.

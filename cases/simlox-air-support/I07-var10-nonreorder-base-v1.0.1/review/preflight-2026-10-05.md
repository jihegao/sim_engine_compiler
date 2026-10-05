# I07.var10 v1.0.1 report-only pre-run review

The v1.0.0 candidate completed both calculations, but its frozen
sole-#108 warning gate stopped before child selected-report export when the
child emitted exact warning #172: “No reorder data defined. ROSIZ ignored.
TEACH-DU-01 / BASE-01.” That v1.0.0 closure remains an excluded diagnostic.
Its 22 raw seals, 22-table roundtrips, zero-error child SXO and byte-equal
control/child event logs were independently checked before this extension.

The new v1.0.1 contract predeclares acceptance of that exact row-specific
warning and requires a single report-only export from the sealed child SXO.
No recalculation, import, model export or write to the original run is
authorized. Independent contract and static reviewers gave final GO after
the runner was strengthened to verify every one of the 22 original raw
size/SHA seals before and after the call, and to require the existing
accepted report selector by byte hash before its idempotent builder check.
The new run path is unoccupied. The runner parses with zero PowerShell
errors and retains SSH0/sshd, global mutex, protected GUI PID13340/session1,
hidden target-only watchdog and before/after source closure.

Frozen v1.0.1 contract SHA-256:
`8b5bf5cc6938e6f2e4d8e57aa3dc45bf0e1dbc6598b032da7b8a85709245074c`.
Final report-only runner SHA-256:
`fa07f883d1fc9e83324ac35ec49331e7b50385cb5c0af08abbc56aa93075bd35`.

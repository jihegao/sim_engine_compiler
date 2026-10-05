# E15.var10 warning/report extension: independent preflight

**GO for one guarded report-only call.** No native process was started
during this review. The unique v1.0.1 run directory was absent.

The current runner SHA-256 is
`143cda37b2a1d1b253bf8b62231cd80bd6b4444842223cc4753ab799c35de9d7`;
PowerShell parsing reports zero AST errors. Its frozen contract SHA-256 is
`9c431f5a8b037c773240acb9aeec4d0d3b3fff6e06cfd228940ede6d9eceb55f`.
All 15 literal source fingerprints match disk: contract, excluded v1.0.0
index/contract/closure/SXO/event and calculation logs, accepted E15 input,
SXO/event/selected report, selector builder and settings, executable and
manual. The v1.0.0 closure has 11 raw files; the runner verifies every
size/SHA before and after the report call. It also requires the existing
selector file's exact hash before invoking the idempotent selector builder.

The contract preserves the v1.0.0 `expected converter error absent`
failure. Its converter actually reported Errors 0, Warnings #108 and #168,
Notes 0, and produced a sealed SXO. The runner checks that exact #168
warning text and diagnostic linkage without reclassifying the old run.

The runner requires session-0 SSH with an `sshd.exe` ancestor, an unused
fixed run ID, nonblocking `Global\SimloxIssue18NativeQueue`, active GUI
PID 13340/session 1/start identity, and a hidden child with a targeted
60-second watchdog. It records source hashes before and after and seals
the new raw files in a fresh immutable closure. The single native command
opens the sealed diagnostic SXO with `-report -rpts -rjexport`; it contains
no calculation, import, model export or save. A nonempty parseable ten-table
JSON report and zero exit are required by the runner.

The prospective 72-bin ItemResults, stock ledger and cross-report
reconciliation remain post-run gates. This review accepts the report
probe's safety and lineage, not a stock-policy conclusion for invalid
ROSIZ or any broader E15.var10 behavior.

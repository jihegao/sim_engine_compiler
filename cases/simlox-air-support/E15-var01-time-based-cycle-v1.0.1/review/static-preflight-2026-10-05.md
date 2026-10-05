# E15.var01 time-cycle report extension: independent preflight

**GO for one guarded report-only export.** No native process was started
during this review, and the fixed v1.0.1 run directory was absent.

The contract SHA-256 is
`d42307744dc8aa8bfcadbb3e0da68149a4b7dcfc5ff93e44189f7b06f1a61857`.
The runner SHA-256 is
`78fe82ad7fae36405e12222c09b87f7f15808ec1bd2ca0e133fc488b3e734640`;
PowerShell parsing reports zero AST errors. All 15 literal source pins
match disk, including the excluded v1.0.0 index/contract/closure/SXO/
event and calculation logs, accepted E15 input/SXO/event/selected report,
selector builder/settings, executable and manual. The 11 original raw
files independently match their closure sizes and SHA-256 values.

The original run remains excluded for `unreviewed converter diagnostic`.
Its actual converter result was Errors 0, Warnings #108 and #376,
Notes 0, with a valid sealed SXO. The new runner checks the exact
`Form: StockAllocation` / record 2 #376 warning for
`TEACH-DU-01 / DEPOT-01`; I evaluated this literal CRLF check against
the sealed calculation log and it passes. The new contract explicitly
discloses that the h10 issue and h16/h17 order/receipt observations
predate this extension.

The runner requires session-0 SSH and an `sshd.exe` ancestor, a unique
fixed run ID, nonblocking global mutex, active protected GUI PID 13340/
session 1/start identity, hidden target-only watchdog, and an existing
selector with exact SHA before the idempotent builder check. It verifies
old raw sizes/SHA both before and after the call, records source hashes
before and after, and seals the new raw files in an immutable closure.
The single command uses `-report -rpts -rjexport` on the sealed v1.0.0
SXO. It contains no calculation, model import/export, or save.

The ten-table selected JSON, 72 depot ItemResults bins, physical stock
ledger and accepted-parent comparison are post-run gates. This GO does
not retroactively accept v1.0.0 or the proposed time-cycle outcome.

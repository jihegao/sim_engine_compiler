# G11.var05: one blank QTY receives the remaining systems

This bounded case compares an explicit `PrelifeData.QTY=2` on the final AGE120 row with a blank QTY on that same row. Both frozen arms deploy four identical aircraft. Their first two rows assign one aircraft each to ages 0 and 60; the blank row in the candidate therefore receives the remaining two. The itemless teaching model retains three referenced OperationProfile rows with `IQTY=0`, so no missions confound the first `CAL100` PMs.

Both guarded native CLI runs completed import, export, calculation, report export, and exact 20 populated-table roundtrip with zero conversion errors and only inherited warnings #108/#126. The Prelife Logs are byte-identical and show `AGE0/AGE60/AGE120/AGE120` with ages 0/60/120/120. The event logs are also byte-identical: aircraft ID1 first PM h40, distinct IDs2 and3 both h80, and ID0 h100; all finish after one hour. Each arm has 208 half-hour System and Stock bins, four PMs, no failures, missions, resource demand or backorders, and terminal ready=4. Author replay passes 188/188 checks and a separate read-only replay passes 21,427/21,427.

The [contract](contract.json), [exact source diff](exact-diff.json), [evidence index](evidence-index.json), [author replay](author-validation.json), [independent verdict](independent-verdict.json), and [CLI sign-off](cli-scope-signoff-2026-10-03.md) document the result. Raw native files stay in ignored local `runs/`, with IDs, sizes and SHA-256 hashes in the index.

This case covers one blank QTY row placed last, four same-type systems, one seed, and first calendar PM only. Row reordering, multiple blanks, over-allocation, installed or stocked item prelife, GUI visual behavior and cross-engine parity remain unverified.

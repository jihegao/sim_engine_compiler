# E15.var09 time-based initial on-hand boundary

The accepted E15.var01 v1.0.1 time-based DU depot observation supplies the equality arm: omitted `ISTOH` and `AINST` resolve to opening stock 4, equal to `STSIZ=4`, with `ROINT=16`. Its original v1.0.0 native run failed a frozen warning-attribution gate; the independently reviewed v1.0.1 report-only extension accepted bounded behavior without recalculation or retroactive promotion of that gate.

This child changes only depot `StockAllocation.ISTOH` from null to 3. The installed SIMLOX 2017 manual, physical page 447, requires time-based `ISTOH >= STSIZ`. A unique guarded SSH session-0 run exactly round-tripped 21 row-containing authored tables, then converter error #377 identified the target depot row: initial stock on hand too small (`ISTOH < STSIZ`). The SXO is four bytes, with no event log or selected report. Warnings #108 and #376 are preserved. Ten local raw files are ignored from Git and sealed by size/SHA-256.

The accepted scope is this one converter rejection. There is no simulated child stock behavior or general lower-bound proof. `contract.json`, the CLI signoff, evidence index, author replay, and independently written `review/independent_replay.py` contain the source pins, exact diagnostic, raw seals, and limits. GUI-only observations K01/K08 remain blocked without capture retries.

# E15.var08 equal-point initial stock: excluded diagnostic

This frozen candidate changed only tracked depot `StockAllocation.ISTOH` from 3 to 2, exactly `STSIZ−ROSIZ=2`, relative to the accepted E15.var07 explicit-three parent. The contract predicted an immediate hour-0 reorder and hour-1 two-item delivery. The native run disproved that prediction. This version is **excluded** from reusable accepted behavior.

The sealed session-0 run completed import, export and calculation with an exact 21 row-containing table roundtrip, no converter errors and a valid SXO. The complete event log opens depot physical IDs0/1 at level two with no hour-0 reorder. At hour 10 ID0 issues, leaving ID1 at level one; one reorder starts with a one-hour lead. At hour 11 a delivery of **three** new physical IDs4/5/6 restores stock to four. The frozen gate stopped before report export. No native stage was rerun and the local raw remains sealed in `runs/`.

The [frozen contract](contract.json), [diagnostic signoff](cli-scope-signoff-2026-10-05.md), review and [evidence index](evidence-index.json) preserve the failed hypothesis and observed event ledger. A later version may export a report from this sealed SXO under a new contract, without claiming this version passed.

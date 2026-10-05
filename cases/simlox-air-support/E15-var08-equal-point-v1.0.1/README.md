# E15.var08 equal-point initial stock: bounded report-only acceptance

This package extends the sealed [v1.0.0 excluded diagnostic](../E15-var08-equal-point-v1.0.0/README.md) with exactly one guarded report export from its original SXO. The v1.0.0 hour-0 reorder hypothesis failed and remains excluded. No model input, import, export or calculation was rerun.

At the valid lower bound `ISTOH=STSIZ−ROSIZ=2`, the depot opens with two physical items and makes no hour-0 order. The inherited hour-10 demand issues ID0, leaving ID1 and one item on hand. One reorder starts at hour 10 and delivers three new IDs4/5/6 at hour 11, restoring stock to four. The first batch is **three**, though `ROSIZ=2`; this single observation does not establish a general batch formula.

The selected report has 72 depot half-hour bins: `STSZ=4`, `STOHA=2` in 20 bins before hour 10, `1` in two bins before hour 11, then `4` in 50 bins through hour 36. One `NRO` appears at hour 10 and `NBO=0` in all bins. Eight other selected tables equal the accepted explicit-three parent. The [new contract](contract.json), [bounded signoff](cli-scope-signoff-2026-10-05.md), independent review and [evidence index](evidence-index.json) pin the original excluded run and new report-only raw. Below-point initial stock and broader E15.var08 behavior remain unverified.

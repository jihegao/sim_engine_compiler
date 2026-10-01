# G01.var06: indexed similar-item stockout

This bounded follow-up derives from the accepted [G01.var06 similar branch](../G01-var06-similar-vs-identical-v1.0.1/cli-scope-signoff-2026-10-01.md). The [contract](contract.json) and [native input](native-input.json) were frozen before the guarded native run. The [exact parent diff](exact-diff.json), [signoff](cli-scope-signoff-2026-10-01.md), and [evidence index](evidence-index.json) define the accepted scope.

Run `build.py` to check the source bytes against the published parent, `describe_diff.py` to verify the three-table delta, and `validate_native.py` to replay author acceptance. The independent reviews are under `review/`. Original SXI/SXO, event log, report, invocation and closure are local under ignored `runs/g01-var06-stockout-v100-ssh-20261001-01/`.

The source reduces `StockAllocation.STSIZ` from two to one per similarity index and extends direct LRU repair from one to 30 hours. In this one fixed-seed run, index 1 consumes its spare after the first failure, then receives a second failure while its first removed item is still under repair. SIMLOX records an explicit index-1 backorder while the untouched index-0 stock still holds one spare; no index-0 item is issued. This is a local observed refusal under the tested stock policy, not a general substitution guarantee.

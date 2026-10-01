# G01.var06: similar versus identical item grouping

This bounded pair derives from accepted [E01](../E01-local-spare-explicit-replacement-v1.0.0/cli-scope-signoff-2026-09-29.md), which has no LRU subitems. One branch uses `ItemStructure.QTYPM=2` with default `Item.NSIMI=1`; the other uses `QTYPM=1` and `NSIMI=2`. Both have `System.FRT=600000` and source `StockAllocation.STSIZ=2`. The [pre-run contract](contract.json), [source diff](exact-diff.json), [signoff](cli-scope-signoff-2026-10-01.md), and [evidence index](evidence-index.json) define the accepted scope.

Run `build.py` to check both frozen input files against E01, `describe_diff.py` to check each exact table delta, and `validate_native.py` to replay author acceptance against the two ignored sealed runs. Separate independent behavior and static reviews are under `review/`. Raw native SXI/SXO, logs, reports, invocation and closure remain local under `runs/`.

The first local v1.0.0 identical branch is retained only as an unpublished diagnostic: a copied checker expected 21 populated source tables although the E01 parent has 20. Native import/calculation/report completed, but the fifth guarded check failed. This v1.0.1 pair uses a corrected checker and fresh sealed runs. Source input bytes remain unchanged.

The native `NSIMI=2` branch creates two similarity indices with a separate stock of two per index, four spares in total; observed demands draw from the matching index. The `QTYPM=2` branch has one stock of two. Both similarity pools were stocked at demand times, so this pair does not test whether a spare from the other index would be refused under shortage. The three aggregate report tables checked are equal across the fixed-seed pair.

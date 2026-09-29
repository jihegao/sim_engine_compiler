# E03 two aircraft sharing one local spare, v1.0.0

This bounded accepted CLI case derives from [accepted E02](../E02-zero-stock-local-backorder-v1.0.0/cli-scope-signoff-2026-09-29.md) and uses the accepted [A03 two-aircraft deployment](../A03-two-aircraft-formation-v1.0.1/cli-scope-signoff-2026-09-29.md). Two one-aircraft missions launch at hour 8. Both aircraft have an installed repairable LRU, but the base has one replacement spare. The [contract](contract.json) predeclares an initial issue and a later backorder for independent native review. The [parent diff](parent-diff.json) gives every changed table. The [dated signoff](cli-scope-signoff-2026-09-29.md) records the observed scope and limits.

Run `python build.py` to verify the frozen input. `python build.py --write` creates the input only if absent. Native run outputs go under ignored `runs/` and are not distributed.
